"""
This file is to calculate a dataset of features from datasets of trips
"""
import sys, os

import numpy as np
import pandas as pd

sys.path.append("../..")
import useful_things as my_util # type: ignore


class FeaturesExtractionConfig:
    """
    A class that store parameters for the function which build a dataset of 
    features
    """

    def __init__(self, dict_labels, feature_calculator, columns_name, file_iter, 
                 save_path):
        """
        dict_labels: a dictionnary that maps each mode present in the database 
        to a label you want
        feature_calculator : the function to call to calculate features of a 
        file
        columns_name: a list of all features' name
        file_iter: an iterator which give the filepath of all files that need 
        to be read
        save_path: the filepath saying where to save the database of features
        """

        self.dict_labels        = dict_labels
        self.feature_calculator = feature_calculator
        self.columns_name       = columns_name
        self.file_iter          = file_iter
        self.save_path          = save_path

def contain_big_hole(df):
    """Retunrn true if there is a "hole" in the trip"""

    old_date = None
    for rows in df.itertuples():

        date = rows.datetime

        if old_date is not None:
            delta_time = (date - old_date).total_seconds()

            if delta_time > 60*15:
                return True

        old_date = date           
    return False


def create_dataset(params:FeaturesExtractionConfig):
    """Return an array of data calculated from the gps files"""

    dataset = []
    labels  = []
    file_discarded = 0

    for file in params.file_iter:
        
        journey = my_util.Journey(file)
        mode    = journey.journey_modes[0][0]

        if len(journey.journey_modes) != 1:
            print("There should be only one mode in the journey " ,end="")
            print(f"but the modes are {journey.journey_modes}")
            continue
        
        # if a mode isn't in the dictionary, we don't consider the file for
        # the database building
        if mode not in params.dict_labels:
            file_discarded += 1
            continue
        
        # If the file is too small we don't consider it
        if journey.gps_data.shape[0] < 10:
            file_discarded += 1
            continue
        
        #if contain_big_hole(journey.gps_data):
        #    file_discarded += 1
        #    continue
                
        dataset.append(
            params.feature_calculator(journey.gps_data)
        )

        labels.append( params.dict_labels[mode] )


    df_features = pd.DataFrame(
        columns=params.columns_name,
        data=dataset
    ).round(5)
        

    df_features["label"] = labels

    df_features.to_csv(params.save_path, index=False)

    print("files discarded :", file_discarded)


def features_extraction_1(df:pd.DataFrame):
    """
    Calculate 10 features. See the config class for more info
    """

    # Features immediately calculable
    total_time = calc_trip_time(df)
    nb_points  = df.shape[0]

    # Features calculable with a first loop
    speeds = []
    delta_times = []
    total_distance = 0

    old_lat, old_lon, old_date = None, None, None
    for rows in df.itertuples():

        lat, lon = rows.latitude, rows.longitude
        date = rows.datetime

        if old_lat is not None:

            distance = my_util.gps_distance(old_lat, old_lon, lat, lon)
            total_distance += distance / 1000

            delta_time = (date - old_date).total_seconds()
            delta_times.append(delta_time / 3600)

            if delta_time > 0.000001:
                # speed is in km/h
                speeds.append(distance / delta_time * 3.6)
            else:
                speeds.append(0.0)

        old_lat, old_lon, old_date = lat, lon, date

    avg_speed_1 = sum(speeds) / len(speeds)
    avg_speed_2 = total_distance / total_time

    min_speed = min(speeds)
    max_speed = np.percentile(speeds, 90) # max(speeds)

    # Features calculable with a second loop
    accelerations = []
    speed_change_rates = []

    for i in range(len(speeds) - 1):

        delta_speed = abs(speeds[i + 1] - speeds[i])

        acceleration = delta_speed / delta_times[i]
        accelerations.append(acceleration)

        if speeds[i] > 0.000001:
            speed_change_rate = delta_speed / speeds[i]
        else:
            speed_change_rate = 0.0
        
        speed_change_rates.append(speed_change_rate)

    max_acceleration = np.percentile(accelerations, 90) #max(accelerations)

    max_speed_change_rate = np.percentile(speed_change_rates, 90) #max(speed_change_rates)
    avg_speed_change_rate = sum(speed_change_rates) / len(speed_change_rates)


    return np.array([
        total_distance, total_time, nb_points, avg_speed_change_rate, 
        max_speed_change_rate, max_acceleration, avg_speed_1, min_speed,
        max_speed, avg_speed_2
    ])


def features_extraction_2(df:pd.DataFrame):
    """
    Calculate 25 features. See the config class for more info
    """

    # Features immediately calculable
    total_time = calc_trip_time(df)
    nb_points  = df.shape[0]

    # Features calculable with a first loop
    speeds        = np.zeros(df.shape[0])
    delta_times   = []
    total_distance = 0

    old_lat, old_lon, old_date = None, None, None
    for rows in df.itertuples():

        lat, lon = rows.latitude, rows.longitude
        date = rows.datetime
            

        if old_lat is not None:

            distance = my_util.gps_distance(old_lat, old_lon, lat, lon)
            total_distance += distance / 1000

            delta_time = (date - old_date).total_seconds()
            delta_times.append(delta_time / 3600)

            if delta_time > 0.000001:
                # speed is in km/h
                speeds[rows.Index] = distance / delta_time * 3.6
            else:
                speeds[rows.Index] = 0.0

        old_lat, old_lon, old_date = lat, lon, date

    ## Average and "max" speeds
    avg_speed_1 = np.mean(speeds)
    avg_speed_2 = total_distance / total_time

    max_speed = np.percentile(speeds, 90) # max(speeds)

    ## Speed distribution
    speed_intervals = [-1, 2, 5, 10, 15, 25, 40, 65, 100, 200, 500]
    categories = pd.cut(speeds, speed_intervals)
    counts = pd.value_counts(categories, sort=False)
    speed_distribution = (counts / len(speeds)).tolist()


    # Features calculable with a second loop
    accelerations = []

    for i in range(len(speeds) - 1):

        delta_speed = abs(speeds[i + 1] - speeds[i])

        # Acceleration is in m/s² in order to keep reasonnable values
        # Here the coefficient is high compared to speeds (3.6 / 12960)
        acceleration = (delta_speed / delta_times[i]) / 12960
        accelerations.append(acceleration)

    ## Max acceleration
    max_acceleration = np.percentile(accelerations, 90) #max(accelerations)

    ## Acceleration distribution
    acceleration_intervals = [-1, 0.1, 0.5, 1.5, 2.5, 4.0, 6.0, 10.0, 20.0]
    categories = pd.cut(accelerations, acceleration_intervals)
    counts = pd.value_counts(categories, sort=False)
    acceleration_distribution = (counts / len(accelerations)).tolist()


    return np.array(
        [
            total_distance, total_time, nb_points, max_acceleration, 
            avg_speed_1, max_speed, avg_speed_2
        ] + 
        speed_distribution + 
        acceleration_distribution
    )


def calc_trip_time(df:pd.DataFrame):
    """
    Return the difference of time in hours between the first and the last 
    point of the dataframe.
    """

    start_time = df.iloc[ 0][my_util.Journey.time]
    end_time   = df.iloc[-1][my_util.Journey.time]

    return (end_time - start_time).total_seconds() / 3600


if __name__ == '__main__':

    """config = FeaturesExtractionConfig(

        dict_labels={
            "walk":0, "bike":1, "car":2, "bus":2, "taxi":2, "train":2, 
             "motorcycle":2,"subway":2, "airplane":2, "boat":2, "run":0
        },
        #

        feature_calculator=features_extraction_1,

        columns_name=[
            "total_distance", "total_time", "nb_points", "avg_speed_change_rate", 
            "max_speed_change_rate", "max_acceleration", "avg_speed_1", "min_speed",
            "max_speed", "avg_speed_2"
        ],

        file_iter=my_util.FileIterator(
            "../../../trip_data/datasets/Geolife Trajectories 1.3/Geolife Trajectories 1.3/transformed_database/",
            1
        ),

        save_path="10_features.csv"
    )"""

    """config = FeaturesExtractionConfig(

        dict_labels={
            "walk":0, "bike":1, "car":2, "bus":2, "taxi":2, "train":2, 
            "subway":2, "airplane":2, "boat":2, "run":0, "motorcycle":2
        },

        feature_calculator=features_extraction_2,

        columns_name=[
            "total_distance", "total_time", "nb_points", "max_acceleration", 
            "avg_speed_1", "max_speed", "avg_speed_2",

            "speed 0-2", "speed 2-5", "speed 5-10", "speed 10-15", "speed 15-25", 
            "speed 25-40", "speed 40-65", "speed 65-100", "speed 100-200", 
            "speed 200-500",

            "acc 0-0.1", "acc 0.1-0.5", "acc 0.5-1.5", "acc 1.5-2.5", 
            "acc 2.5-4.0", "acc 4-6", "acc 6-10", "acc 10-20"
        ],

        file_iter=my_util.FileIterator(
            "../../../trip_data/datasets/Geolife Trajectories 1.3/Geolife Trajectories 1.3/transformed_database/",
            1
        ),

        save_path="distrib_features.csv"
    )"""

    """config = FeaturesExtractionConfig(

        dict_labels={
            "walk":0, "bike":1, "car":2, "bus":2, "luas":2, "dart":2
        },
        #

        feature_calculator=features_extraction_1,

        columns_name=[
            "total_distance", "total_time", "nb_points", "avg_speed_change_rate", 
            "max_speed_change_rate", "max_acceleration", "avg_speed_1", "min_speed",
            "max_speed", "avg_speed_2"
        ],

        file_iter=my_util.FileIterator(
            "../../../trip_data/2024_unimodals/data/"
        ),

        save_path="10_features_from_our_data.csv"
    )"""

    config = FeaturesExtractionConfig(

        dict_labels={
            "walk":0, "bike":1, "car":2, "bus":2, "luas":2, "dart":2
        },

        feature_calculator=features_extraction_2,

        columns_name=[
            "total_distance", "total_time", "nb_points", "max_acceleration", 
            "avg_speed_1", "max_speed", "avg_speed_2",

            "speed 0-2", "speed 2-5", "speed 5-10", "speed 10-15", "speed 15-25", 
            "speed 25-40", "speed 40-65", "speed 65-100", "speed 100-200", 
            "speed 200-500",

            "acc 0-0.1", "acc 0.1-0.5", "acc 0.5-1.5", "acc 1.5-2.5", 
            "acc 2.5-4.0", "acc 4-6", "acc 6-10", "acc 10-20"
        ],

        file_iter=my_util.FileIterator(
            "../../../trip_data/2024_unimodals/data/"
        ),

        save_path="distrib_features_from_our_data.csv"
    )

    create_dataset(config)

