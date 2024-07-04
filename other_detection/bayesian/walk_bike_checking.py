"""
This file is to check a trip when the mode stated by a user is walk or bike
using the bayesian method
"""

import os, sys

import pandas as pd
import numpy as np


sys.path.append("../..")
import useful_things as my_util  # type: ignore
import multi_modal               # type: ignore


class BayesianChecker:
    """
    A trip classifier that use the Bayes' formula.

    It is configured to classify the trips into three categories : walk, bike
    and other. It takes as a parameter a file of statistics which give for the 
    three categories the probability of being in a speed intervall. There are 
    intervalls for every 2 km/h starting from 0 and ending at 46. If a speed is 
    greater than 46, we consider the speed equal to 46. These element give the 
    meaning of the _speed_to_index method. These intervalls are probably not 
    the best and could be changed but the method gives good result so there is 
    no emergency. Other comment : the sum of the numbers in a column should be 
    equal to 1 but in pratice it's not the case as it doesn't raise any other
    problem then that... not very rigorus but it works :)"""

    def __init__(self, stats_path=None):
        """
        stats_path: a path the a file containing statistics about the 
        probabilities of having a speed according a mode of transport. If no 
        value is given the default file is taken
        """

        if stats_path is None:
            parent_folder = os.path.dirname(os.path.abspath(__file__)) + os.sep
            stats_path = parent_folder + "probability_WCO.txt"

        self.speeds_stats = np.array(
            pd.read_csv(stats_path)[["walk", "cycle", "other"]]
        )
    
    def _speed_to_index(self, speed) -> int:
        """
        Convert a speed into it's associated index in the bayesian checking

        For example, a speed of 18.5 km/h will give 9 as index which correspond 
        to the intervall [18, 20] in the array self.speeds_stats
        """

        return min(int(speed / 2), 23)


    def calc_probabilities(self, speeds:list):
        """Return a vector of probability for the walk, bike and other modes"""

        p = np.array([0.33, 0.33, 0.34])

        for speed in speeds:

            stat = self.speeds_stats[self._speed_to_index(speed)]
            p    = p * stat / np.dot(p, stat)

        p = np.vectorize(lambda x: round(x, 2))(p)

        return p
    
    def check(self, speeds:list, expected_mode:str) -> bool:
        """
        Return a boolean indicating if the mode predicted matches the 
        expected_mode
        """

        dico_index_modes = {0: "walk", 1: "bike", 2: "other"}

        p = self.calc_probabilities(speeds)

        index_max = np.argmax(p)

        return dico_index_modes[index_max] == expected_mode



def bayesian_checking(mode:str, speeds:list, bayesian_checker:BayesianChecker):
    """Check a trip with a bayesian method"""

    p = bayesian_checker.calc_probabilities(speeds)

    if mode in ("walk", "bike"):
        category = mode
    else:
        category = "other"

    if bayesian_checker.check(speeds, category):
        is_ok = "ok ✔️"
    else:
        is_ok = "NO ❌"

    print(f"Mode : {mode}, probas : {p}, check : {is_ok}")




def test_bayesian_method():
    """Read the trips collected and apply the bayesian method on them"""

    folder = "../../../trip_data/2024/"
    mmd = multi_modal.MultiModalDetection()
    trips_tested = 0

    bayesian_checker = BayesianChecker("probability_WCO.txt")

 
    for file in os.listdir(folder):

        print("file : ", file)
        journey = my_util.Journey(folder + file)


        speeds = my_util.calc_speed(journey.gps_data)

        
        trips_detected = mmd.multi_modal_detection(
            journey.journey_modes, journey.gps_data, True
        )

        for i, trip_detected in enumerate(trips_detected):
            
            mode = journey.journey_modes[i][0]
            print(f"The mode is '{mode}' prediction : ")

            if trip_detected.gps_index_start is not None:

                start = trip_detected.gps_index_start
                end   = trip_detected.gps_index_end

                bayesian_checking(mode, speeds[start:end], bayesian_checker)

                trips_tested += 1

            else:
                print("trip wasn't detected")

        print("\n")
    print("Trips tested : ", trips_tested)

                    

if __name__ == '__main__':
    test_bayesian_method()