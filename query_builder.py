from collections import Counter
import json


def search_tribes_by_relevancy_query(user_vector, coordinates):
    # Algorithm is
    #
    # match tribes according to interest tags
    # filtering out the ones not for your age if you have age
    # filtering out the ones not in your location if we know where you are
    # filtering out the ones not for your gender if tribe has gender
    # filtering out the huperlocal ones if we dont where you are (this is done implicitly at the moment by setting the coordinates in the North Pole)
    # boosting the hyperlocal ones if we know where you are
    #
    # Note that
    #   in tribe document:
    #       location is REQUIRED
    #       age      is REQUIRED -> OPTIONAL soon
    #       gender   is OPTIONAL
    #   in user document:
    #       location is OPTIONAL
    #       age      is OPTIONAL
    #       gender   is OPTIONAL
    #
    # TODO
    # 
    # location boosting
    #
    matching_query = {
        "query": {
            "function_score": {
                "query": interests_query(user_vector['dna']),
                "functions": [ 
                    custom_score
                    for custom_score in [
                        location_scoring(coordinates),
                        age_scoring(user_vector['age']),
                        gender_scoring(user_vector['gender'])]
                    if custom_score
                ],
                "boost_mode": "multiply",
                "max_boost": 1,
                "score_mode": "multiply"
            }
        }
    }
    return matching_query

def interests_query(interests):
    hashable_interests = [json.dumps(interest) for interest in interests]
    weigted_vector = Counter(hashable_interests)
    keys = [key for (key, _) in weigted_vector.most_common(1000)]
    i_query = {
        "bool": {
            "should": [
                {
                    "constant_score": {
                        "boost": weigted_vector[k],
                        "query": {
                            "match": json.loads(k)
                        } 
                    } 
                } for k in keys 
            ]
        }
    }
    return i_query

def gender_scoring(gender):
    if not gender:
        return None
    # TODO: make sure that tribes with no genders are not filtered out
    score =  {
        "script_score": {
            "params": {
                "gender": gender
            },
            "script": "\
                if (gender in doc['genders'].value) {\
                    score = 1\
                } else {\
                    score = 0\
                };\
                score"
        }
    }
    return score

def location_scoring(coordinates):
    if not coordinates:
        return None
    score = {
        "script_score": {
            "params": {
                "lat": coordinates['lat'],
                "lon": coordinates['lon']
            },
            "script": "\
                radius = doc['location.radius'];\
                distance = doc['location.ll'].arcDistance(location);\
                \
                decay = (2 * radius - distance) / radius;\
                boosting = 200 / radius;\
                \
                if (distance < radius) {\
                    score = _score + boosting\
                } else if (distance < 2 * radius) {\
                    score = _score * decay + boosting\
                } else {\
                    score = 0\
                };\
                score"
        }
    }
    return score


def age_scoring(age):
    if not age:
        return None
    score = {
        "script_score": {
            "params": {
                "age": age,
            },
            "script": "\
                min_age = doc['ageRange.min'];\
                max_age = doc['ageRange.max'];\
                \
                if (min_age < age && age < max_age) {\
                    score = 1\
                } else {\
                    years_out_of_range = min_age - age ? age < min_age : age - max_age;\
                    if (years_out_of_range < 3) {\
                        score = (3 - years_out_of_range) / 3\
                    } else {\
                        score = 0\
                    };\
                };\
                score"
        }
    }
    return score

