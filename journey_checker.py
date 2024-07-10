"""
Implementation of the algorithm to check a journey.

It starts by looking public transports using GTFS files and then deduce
private mode of transports. This is the first part.
Next, for each part of the journey we do a specific treatment :

- if it's a public transport we don't do anything more because we already found 
the line. It would be necessary to use realtime data to check trips on bus to 
distinguish from cars, but realtime data handling is more complex and need 
more work especially to ensure reproductible results with tests.

- if it's a private transport we use a classification algorithm except if it's
a car since we don't need to check that. For now, the bayesian method has 
given the best results so we'll use it. 
"""


from . import multi_modal
import useful_things as my_util
import other_detection.bayesian.walk_bike_checking as bayes

mmd = multi_modal.MultiModalDetection()
bayesian_checker = bayes.BayesianChecker()

def check_journey(journey:my_util.Journey, verbose=False):
    """
    Return a list of booleans indicating for each trip if it was verified or 
    not and second list for the inter trips
    """
    

    list_checked_modes = []

    speeds = my_util.calc_speed(journey.gps_data)

    if verbose: print("--- MULTI-MODAL SPLITING ---")
    trips_detected = mmd.multi_modal_detection(
        journey.journey_modes, journey.gps_data, verbose
    )

    if verbose: print("\n\n--- CHECKING EACH TRIP ---")
    for i, trip_detected in enumerate(trips_detected):
            
        mode = journey.journey_modes[i][0]
        if verbose: print(f"\t- The mode is {mode}, ", end="")

        if mode in ("walk", "bike"):
            
            if trip_detected.has_a_valid_trip():
                if verbose: print(f"we use a classification algorithm : ", end="")

                start = trip_detected.gps_index_start
                end   = trip_detected.gps_index_end

                checked = bayesian_checker.check(speeds[start:end], mode)

                if verbose:
                    if checked: print("checked")
                    else:       print("not checked")

            else:
                if verbose: print("it wasn't found previously")
                checked = False

        elif mode == "car":
            if verbose: print("it doesn't need any checking")
            checked = True

        elif mode in ("luas", "dart", "bus"):
            
            if trip_detected.has_a_valid_trip():
                if verbose: print("it was found in the previous step")
                checked = True
            else:
                if verbose: print("it wasn't found in the previous step")
                checked = False

        else:
            print("unknown mode")
            checked = False

        list_checked_modes.append(checked)


    if verbose: print("\n\n--- CHECKING INTER-TRIPS ---")

    # Minimal number of points required to perform a check between two trips
    MINIMAL_SPACE = 20
    list_checked_inter_trips = []

    for i in range(len(trips_detected) + 1):
        
        # Getting the start and end of an inter-trip depending on it's position 
        # in the journey : before the first trip, between two trips or after 
        # the last trip
        if i == 0:
            start = 0
            end   = trips_detected[0].gps_index_start

            mode = journey.journey_modes[0][0]
            if verbose: print(f"\t- Before {mode}: ", end="")

        elif i == len(trips_detected):
            start = trips_detected[i - 1].gps_index_end
            end   = len(speeds)

            mode = journey.journey_modes[i-1][0]
            if verbose: print(f"\t- After {mode}: ", end="")

        else:
            start = trips_detected[i-1].gps_index_end
            end   = trips_detected[i  ].gps_index_start

            mode_1 = journey.journey_modes[i-1][0]
            mode_2 = journey.journey_modes[i  ][0]
            if verbose: print(f"\t- Between {mode_1} and {mode_2}: ", end="")

        # Depending on the number of point in the inter-trip we check if it's a 
        # walk part or not
        diff = end - start
        if diff >= MINIMAL_SPACE:

            checked = bayesian_checker.check(speeds[start:end], "walk")

            if verbose:
                print(f"checking ({diff} points)... ", end="")
                if checked: print("ok")
                else      : print("NO")
        else:
            if verbose: print(f"no enough points ({diff})")
            checked = True

        list_checked_inter_trips.append(checked)

    return list_checked_modes, list_checked_inter_trips


def analyse_journey(journey_file_path):

    journey = my_util.Journey(journey_file_path)
    list_checked_modes, list_checked_inter_trips = check_journey(journey, True)
    result = all(list_checked_modes, list_checked_inter_trips)
    return result


if __name__ == "__main__":
    trip_folder = "../trip_data/2024/"

    journey = my_util.Journey(trip_folder + "bus-16_luas-Red#9-06.json")

    print(check_journey(journey, True))

