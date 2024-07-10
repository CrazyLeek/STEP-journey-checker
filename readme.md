
# Home of the algorithm to check users' journeys

To use it from an external point of view, the fonction to call is in the file 
'journey_checker.py' and is named 'check_journey'


## Overview of the algorithm

The modes considered are :
- walk
- bike
- car
- luas (tramay)
- dart (train)
- bus

The algorithm takes as input a list of GPS coordinates (time, longitude, 
latitude) and a list of mode of transports stated by the user such as ('walk', 
'bus 1', 'bus 2').

The algorithm is divided in three parts :
1. Multimodal journey detection: as a journey can be composed of several mode 
  of transports, each part has to be identified

2. Trip checking: once each trip has been identified in step 1, they are 
  verified

3. Check inter trips: points between two modes of transport (particularly 
  between two modes of public transports when users are supposed to walk and 
  this mode isn't explicitly declared by them) are checked assuming they can 
  only be walk

![Overview of the algorithm](readme_assets/algo_journey_checking.svg#center)

The algorithm use to main features :
- a classification algorithm : two methods were tested (a bayesian and a machine 
  learning method). Currently, the method used is the bayesian one.
- a public transport search : we use data issued by the city of Dublin to 
  verify that commuters' points match public routes.
