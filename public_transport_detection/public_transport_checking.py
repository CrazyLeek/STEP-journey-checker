"""
The goal of this file is to identify a public transport line
"""

import sys, os

"""import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import haversine as hs"""

sys.path.append("..")
import useful_things as my_util # type: ignore


class PublicTripDetected():
    """
    A class to store data about a public transport trip which has been detected 
    in the GPS data
    """

    ATTRIBUTES = ["route", "matched_stops", "first_stop", "last_stop", 
                  "gps_index_start", "gps_index_end"]
    

    def __init__(self):
        """Create all values with a None"""
        self.reset_values()


    def set_record(self, route=None, matched_stops=None, first_stop=None,
                   last_stop=None, gps_index_start=None, gps_index_end=None):
        """
        Method to change attributes. If a value is not specified for an 
        attribute, it won't change.
        """

        params = [route, matched_stops, first_stop, last_stop, 
                  gps_index_start, gps_index_end]
        
        for i, attribute in enumerate(PublicTripDetected.ATTRIBUTES):

            if params[i] is not None:
                setattr(self, attribute, params[i])


    def reset_values(self):
        """Set all attributes to None"""

        for attribute in PublicTripDetected.ATTRIBUTES:
            setattr(self, attribute, None)
    
    def copy_values_from(self, other):
        """
        Copy all the values of the 'other' object into this object
        """

        for attribute in PublicTripDetected.ATTRIBUTES:
            setattr(self, attribute, getattr(other, attribute))

    def print(self, gtfs_data):
        """Print a trip in the std output"""
        
        print(f"{self.last_stop - self.first_stop + 1} stops ", end="")
        print("from GPS position ", end="")
        print(f"{self.gps_index_start} to {self.gps_index_end}")

        for i in range(self.first_stop, self.last_stop + 1):

            stop = gtfs_data \
                    .get_stops() \
                    .query(f"stop_id == '{self.route[i]}'")
            
            print(f"Stop number {i + 1} : ", end="")
            print(stop.iloc[0]["stop_name"])

    def has_a_valid_trip(self):
        """Return true if a trip has been identified"""

        return (self.gps_index_start is not None) and \
               (self.gps_index_end   is not None)




class PublicTripDetector():
    """
    A class mainly created to group the functions used to detect a public trip 
    and reduce the number of arguments in the methods
    """

    def __init__(self):
        
        # Contains gtfs data for all public transports
        self.all_gtfs_data = my_util.PUBLIC_TRANSPORT_DATA

        # This attribute is set when the mode of transport is given in the
        # find_public_line method. It will be used by all methods which work  
        # with gtfs data 
        self.gtfs_data = None


    def get_route_id_from_route_name(self, route_name:str):
        """
        Returns the id of a route from it's name.
        
        For example, if route's name is 'A', '53' or 'blue' it will return 
        something like '5645_65459'
        """

        return self.gtfs_data \
                .get_routes() \
                .query(f"route_short_name == '{route_name}'") \
                .iloc[0]["route_id"]


    def get_trips_id_from_route_id(self, route_id):
        """
        Returns the list of the trips done by a route.
        
        For example, from a route_id with value '4021_65459' will return a list 
        like '[4021_10000, 4021_10001, 4021_10002, 4021_10003, 4021_10004]'
        """

        return self.gtfs_data \
                .get_trips() \
                .query(f"route_id == '{route_id}'") \
                ["trip_id"] \
                .tolist()


    def get_public_info(self, route_name:str):
        """
        Return a list of all trips done in a route where a trip is a list of 
        stop ids. 
        Most of the time there should be only two trips for a route
        as it is the normal case, but the luas red line has three terminus for 
        example so we have at least four trips here."""
        
        # Get the id of the route
        route_id = self.get_route_id_from_route_name(route_name)
        
        # Get all the id of the trips done by the route
        trip_ids = self.get_trips_id_from_route_id(route_id)


        # Filter the stops which are related to the route and group them by 
        # trip_id
        stops = self.gtfs_data \
                    .get_stop_times() \
                    .query("trip_id in @trip_ids") \
                    .groupby("trip_id")

        # Look if there are trips which don't have the same stops
        sub_routes = []
        for _, group in stops:
            
            stops_list = group["stop_id"].tolist()

            already_here = any(
                map(
                    lambda x: x == stops_list,
                    sub_routes
                )
            )

            if not already_here:
                sub_routes.append(stops_list)

        # Print all the trips found in the same route
        """for sub_route in sub_routes:

            for stop_id in sub_route:
                stop = self.gtfs_data \
                        .get_stops() \
                        .query(f"stop_id == '{stop_id}'")
                print(stop.iloc[0]["stop_name"])

            print(sub_route)
            print("")"""

        return sub_routes


    def get_stop_positions(self, stops):
        """Return the list of the stops' coordinates"""

        res = []

        for stop_id in stops:
            stop = self.gtfs_data \
                    .get_stops() \
                    .query(f"stop_id == '{stop_id}'")

            res.append((stop.iloc[0]["stop_lat"], stop.iloc[0]["stop_lon"]))

        return res


    def get_nearest_stop_from_point(self, lat, lon, stop_positions) -> tuple[int, float]:
        """
        Return the index and the distance of the nearest stop from the point 
        (lon, lat)
        """

        min_distance = my_util.gps_distance(lat, lon, *stop_positions[0])
        min_i = 0

        for i in range(len(stop_positions)):
            
            distance = my_util.gps_distance(lat, lon, *stop_positions[i])

            if distance < min_distance:
                min_i = i
                min_distance = distance

        return min_i, min_distance


    def find_trip_from_gps_data(self, routes, gps_data):
        """
        Find among the routes (routes) the one which get the most stops matched 
        with the user's data (gps_data)
        """

        trip      = PublicTripDetected()
        best_trip = PublicTripDetected()
        best_trip.set_record(matched_stops=0)
        

        for route in routes:

            stop_positions = self.get_stop_positions(route)
            trip.reset_values()

            for i, row in gps_data.iterrows():

                lat = row["latitude"]
                lon = row["longitude"]

                current_stop, distance = self.get_nearest_stop_from_point(
                    lat, lon, stop_positions
                )

                if distance < 125:

                    if trip.first_stop is None:
                        trip.set_record(
                            first_stop      = current_stop,
                            last_stop       = current_stop,
                            gps_index_start = i,
                            gps_index_end   = i
                        )
        
                    else:
                        if current_stop == trip.last_stop + 1:
                            trip.set_record(
                                last_stop     = current_stop,
                                gps_index_end = i
                            )
                            
                        
                        elif current_stop < trip.last_stop:
                            # This case should only occur when the line taken
                            # by the user is 'read' in the reverse order
                            #print("Near from a passed stop...")
                            pass
                        
                        elif current_stop > trip.last_stop + 1:
                            # Weird
                            #print("A stop is missing...")
                            pass

            # We save the route and the stops associated if the number of stops 
            # matched is greated than the max number
            if trip.first_stop is not None:
                trip.set_record(
                    matched_stops=trip.last_stop - trip.first_stop,
                    route=route
                )

                if trip.matched_stops > best_trip.matched_stops:
                    best_trip.copy_values_from(trip)

        # Print a recap for the best route
        """if best_trip.route is None:
            print("No passage on this line was found")
        
        else:
            print("Here's the best trip detected")
            best_trip.print(gtfs_data)"""
        
        return best_trip
            

    def find_public_line(self, gps_data, mode, line) -> PublicTripDetected:
        """It's the only method that should be called outside the class
        gps_data : the user's data
        mode : mode of transport e.g. 'bus', 'luas' or 'dart'
        line : the line's name like '4' or 'Green'
        return an object that describe the identified trip"""

        self.gtfs_data = self.all_gtfs_data[mode]
        routes = self.get_public_info(line)
        return self.find_trip_from_gps_data(routes, gps_data)



def test_public_transport_detection():
    """
    Read all the trips containing a public transport an try to find the stops
    taken.
    """

    folder = "../../trip_data/migrated_data/"
    public_trip_detector = PublicTripDetector()

    for file in os.listdir(folder):

        journey = my_util.Journey(folder + file)

        for trip in journey.journey_modes:

            mode = trip[0]

            if mode in ("luas", "dart", "bus"):

                if mode == "dart":
                    transport_line = "DART"
                else:
                    transport_line = trip[1]

                print(f"{file} : trying to detect stops for ", end="")
                print(f"{transport_line} {mode} line :")

                trip_detected = public_trip_detector.find_public_line(
                    journey.gps_data, mode, transport_line
                )

                if trip_detected.route is not None:
                    print(f"{trip_detected.last_stop - trip_detected.first_stop + 1} stops ", end="")
                    print("from GPS position ", end="")
                    print(f"{trip_detected.gps_index_start} to {trip_detected.gps_index_end}")

                else:
                    print("No transport detected --end of function")
                    

                print()

if __name__ == "__main__":
    test_public_transport_detection()