"""
This file aims to deal with multi-modal journeys.

We have two types of transports :
    - private : walk, bike, car
    - public : luas, dart, bus

When dealing with a multi-modal journey, finding where public transports have
been taken is easy because we know where they are supposed to be and so we
can simply match the gps positions recorded by the user to the stops. The 
harder part is about finding private transports since they don't have a
pre-defined path.

However, public transport can help us finding private transports. Suppose we
have a journey like car -> bus. Since we can know where the bus was taken
we can simply figure out where the car where taken, it's just the part before
the bus. The same applies with more complex journeys like bus1 -> bus2 -> 
walk -> dart. The walking part is between the bus and dart parts. Hence, the 
only tricky case is when having two consecutive private transports such as
car -> walk. This last case is not handled currently.
"""

import itertools
import math

import useful_things as my_util # type:ignore
import public_transport_detection.public_transport_checking as ptc 
import other_detection.bayesian.walk_bike_checking as bayesian

class PrivateTripDetected():
    """Store information about a private trip"""

    def __init__(self):

        self.gps_index_start = None
        self.gps_index_end   = None

    def has_a_valid_trip(self) -> bool:
        """Return true if a trip has been identified"""

        return (self.gps_index_start is not None) and \
               (self.gps_index_end   is not None)


class MultiModalDetection:
    """The class that handle the detection of a public transport line"""

    def __init__(self, all_gtfs_data:dict=None):

        self.public_trip_detector = ptc.PublicTripDetector()
        self.bayesian_checker     = bayesian.BayesianChecker()
        if all_gtfs_data is not None:
            self.public_trip_detector.all_gtfs_data

        # These attributes are set when the main function is called
        self.verbose = False
        self.journey = []
        self.trips_detected = []

    def public_transport_detection(self, trip_info):

        mode = trip_info[0]

        if mode == "dart":
            line = "DART"
        else:
            line = trip_info[1]

        trip_found = self.public_trip_detector \
                         .find_public_line(self.gps_data, mode, line)


        if self.verbose:

            print(f"\t- {mode} {line} : ", end="")

            if trip_found.route is not None:
                
                print(f"{trip_found.last_stop - trip_found.first_stop + 1} stops ", end="")
                print("from GPS position ", end="")
                print(f"{trip_found.gps_index_start} to {trip_found.gps_index_end}")

            else:
                print("no transport detected")
        
        
        return trip_found


    def deduce_point_from_previous_trip(self, trip_index):
        """
        Copy the end point of a previous trip and put the number plus one in 
        the start point the next trip
        """

        split = self.trips_detected[trip_index - 1].gps_index_end + 1
        self.trips_detected[trip_index ].gps_index_start = split

        return split

    def deduce_point_from_next_trip(self, trip_index):
        """
        Copy the start point of a next trip and put the number minus one in 
        the start point the previous trip
        """

        split = self.trips_detected[trip_index + 1].gps_index_start - 1
        self.trips_detected[trip_index ].gps_index_end = split

        return split
        

    def look_side_trip(self, trip_index, direction):
        """
        Examine the next or previous trip in order to deduce the starting or 
        ending of a private trip
        """

        if direction == "previous":
            side_index = trip_index - 1
            deduce_point = self.deduce_point_from_previous_trip

        elif direction == "next":
            side_index = trip_index + 1
            deduce_point = self.deduce_point_from_next_trip
        
        else:
            print(f"side_index {side_index} is unknow")
            return


        if self.journey[side_index][0] in ("luas", "dart", "bus"):

            if self.trips_detected[side_index].route is not None:

                split = deduce_point(trip_index)

                if self.verbose:
                    print(f"{direction} trip is public, deduced point is {split} ", end="")
            else:
                if self.verbose:
                    print(f"{direction} trip is public but wasn't found in previous step ", end="")

        else:
            if self.verbose:
                print(f"{direction} trip is private, ", end="")

        
    def multi_modal_detection(self, journey, gps_data, verbose=False):
        """Try to detect a multi-modal trip"""

        self.verbose  = verbose
        self.journey  = journey
        self.gps_data = gps_data

        self.trips_detected = []

        if self.verbose:
            print(f"journey : {self.journey}")
            print("--- FIRST ROUND ---")


        for trip in self.journey:

            mode = trip[0]

            if mode in ("luas", "dart", "bus"):
                
                trip_found = self.public_transport_detection(trip)

                self.trips_detected.append(trip_found)

            elif mode in ("walk", "bike", "car"):

                if verbose: print(f"\t- {mode} : nothing to do yet")
                self.trips_detected.append(PrivateTripDetected())

            else:
                print(f"unknown mode {mode}")


        if verbose: print("--- SECOND ROUND ---")
        for i, trip in enumerate(journey):
            mode = trip[0]

            if mode in ("walk", "bike", "car"):

                if self.verbose: print(f"\t- {mode} : ", end="")
                
                if i > 0: # there is a previous trip 
                    self.look_side_trip(i, "previous")

                else: # it's the first trip
                    self.trips_detected[0].gps_index_start = 0

                    if self.verbose:
                        print("first trip, start point set to 0", end=", ")


                if i + 1 < len(journey): # there is a next trip
                    self.look_side_trip( i, "next")
                
                else: # it's the last trip
                    self.trips_detected[-1].gps_index_end = gps_data.shape[0] - 1

                    if self.verbose:
                        print("last trip, end point set to ", end="")
                        print(gps_data.shape[0] - 1, end="")
                    
                if self.verbose: print("")
            else:
                if verbose:
                    print(f"\t- {mode} : GPS position from ", end="")
                    print(f"{self.trips_detected[i].gps_index_start} to ", end="")
                    print(f"{self.trips_detected[i].gps_index_end}")


        if verbose: print("--- THIRD ROUND ---")
        speeds = my_util.calc_speed(gps_data)
        i = 0
        nb_trips = len(journey)
        while i < nb_trips:
            
            consecutive_private_trips = 0
            while i < nb_trips and journey[i][0] in ("walk", "bike", "car") :
                consecutive_private_trips += 1
                i += 1

            if consecutive_private_trips >= 2:
                start = i - consecutive_private_trips
                end   = i - 1

                if verbose:
                    print(f"\t- {end - start + 1} consecutive private ", end="")
                    print(f"trips detected from position {start} to {end}")

                separations = itertools.combinations(
                    range(
                        self.trips_detected[start].gps_index_start + 10, 
                        self.trips_detected[end].gps_index_end,
                        30
                    ),
                    consecutive_private_trips - 1
                )
                
                best_separation = (0.0, [])
                for separation in separations:
                    sorted(separation)
                    trips_test = []

                    trips_test.append(
                        (
                            self.trips_detected[start].gps_index_start, 
                            separation[0]
                        )
                    )
                    for j in range(consecutive_private_trips - 2):
                        trips_test.append(
                            (separation[j], separation[j + 1])
                        )

                    trips_test.append(
                        (
                            separation[-1], 
                            self.trips_detected[end].gps_index_end
                        )
                    )

                    probability = 1.0
                    for j, (trip_start, trip_end) in \
                        zip(range(start, end + 1), trips_test):

                        p = self.bayesian_checker.calc_probabilities(
                            speeds[ trip_start : trip_end ]
                        )

                        if   journey[j][0] == "walk": probability *= p[0]
                        elif journey[j][0] == "bike": probability *= p[1]
                        elif journey[j][0] == "car" : probability *= p[2]
                        else: print(f"Unknown mode : {journey[j][0]}")

                    if probability > best_separation[0]:
                        best_separation = (probability, trips_test)


                if verbose:
                    print(f"\t  Best proba found : {best_separation[0]}")

                for j, (trip_start, trip_end) in \
                    zip(range(start, end + 1), best_separation[1]):

                    self.trips_detected[j].gps_index_start = trip_start
                    self.trips_detected[j].gps_index_end   = trip_end

                    if verbose:
                        print(f"\t  {journey[j][0]} : {trip_start} to {trip_end}")
                        
            i += 1

        return self.trips_detected     


def test_multi_modal_detection():
    """
    Read all the trips containing a public transport an try to find the stops
    taken.
    """

    mmd = MultiModalDetection()

    folder = "../trip_data/2024/"
    file = folder + "bike_walk_bike#07-04.json"

    journey = my_util.Journey(file)

    print(f"Analysing {file} ({journey.gps_data.shape[0]} points): ")

    mmd.multi_modal_detection(
        journey.journey_modes, 
        journey.gps_data,
        True
    )

    """for file in my_util.FileIterator(folder, show_progress=False):

        journey = my_util.Journey(file)

        print(f"Analysing {file} ({journey.gps_data.shape[0]} points): ")

        mmd.multi_modal_detection(
            journey.journey_modes, 
            journey.gps_data,
            True
        )

        print("\n")"""


if __name__ == '__main__':
    test_multi_modal_detection()
