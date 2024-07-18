"""
This file is a collection of useful things (functions, classes, etc) to
solve the problem of checking a user's journey
"""


import os, json, io
import dateutil.parser
from datetime import datetime

import pandas as pd
import haversine

class GtfsData:
    """
    A structure to store GTFS info about a transport mode e.g. bus or luas
    For more info see: https://gtfs.org/schedule/reference/
    """

    def __init__(self, folder:str):
        """
        folder: a GTFS folder containing the appropriate files e.g routes.txt,
        trips.txt, etc. It must end by a folder separator like '/' or '\\' .
        """

        self.folder = folder

        # All the data is lazy loaded, i.e. the files won't be read until a 
        # first call is made to a getter
        self.routes     = None
        self.trips      = None
        self.shapes     = None
        self.stop_times = None
        self.stops      = None


    def read_csv(self, filename:str) -> pd.DataFrame:
        """Read a csv file and return the associated DataFrame"""

        return pd.read_csv(self.folder + filename, low_memory=False)
    

    def get_routes(self) -> pd.DataFrame:
        """Return the dataframe containing data of the routes.txt"""

        if self.routes is None:
            self.routes = self.read_csv("routes.txt")

        return self.routes
    

    def get_trips(self) -> pd.DataFrame:
        """Return the dataframe containing data of the trips.txt"""

        if self.trips is None:
            self.trips = self.read_csv("trips.txt")

        return self.trips
    

    def get_shapes(self) -> pd.DataFrame:
        """Return the dataframe containing data of the shapes.txt"""

        if self.shapes is None:
            self.shapes = self.read_csv("shapes.txt")

        return self.shapes
    

    def get_stop_times(self) -> pd.DataFrame:
        """Return the dataframe containing data of the stop_times.txt"""

        if self.stop_times is None:
            self.stop_times = self.read_csv("stop_times.txt")

        return self.stop_times
    

    def get_stops(self) -> pd.DataFrame:
        """Return the dataframe containing data of the stops.txt"""

        if self.stops is None:
            self.stops = self.read_csv("stops.txt")

        return self.stops

parent_folder = os.path.dirname(os.path.abspath(__file__))
PUBLIC_TRANSPORT_DATA = {
        "bus" : GtfsData(parent_folder + "/GTFS_Dublin_Bus/"),
        "luas": GtfsData(parent_folder + "/GTFS_luas/"),
        "dart": GtfsData(parent_folder + "/GTFS_rail/")
    }

class Trip:
    """Represent an unimodal trajectory"""

    PUBLIC_MODES  = ["bus", "dart", "luas"]
    PRIVATE_MODES = ["walk", "bike", "car"]
    ALL_MODES = PUBLIC_MODES + PRIVATE_MODES

    def __init__(self, mode, line=None):
        """
        mode: represent a mode of transport e.g. car, bus, walk etc.
        line: if the mode is a public transport, 'line' contains the name of
        the line e.g '1', '2', 'A', 'Green' etc.
        """

        if mode not in Trip.ALL_MODES:
            raise ValueError(f"Unknown mode '{mode}'")
        self.mode = mode

        self.line = line

    def get_mode(self) -> str:
        """Return the mode of transport"""
        return self.mode
    
    def get_line(self) -> str | None:
        """Return the line of transport"""
        return self.line

    def get_mode_and_line(self) -> str:
        """
        Return the mode and the line of transport in a 'pretty' string. For 
        example if the mode is private, the line isn't displayed"""

        if self.mode in Trip.PUBLIC_MODES and self.mode != "dart":
            line = "-{self.line}"
        else:
            line = ""

        return self.mode + line
    

class Journey:
    """Store a journey loaded from a file"""

    lon  = "longitude"
    lat  = "latitude"
    time = "datetime"
    time_str = "created"

    def __init__(self, filename):

        self.journey_modes  = None
        self.gps_data = None

        self.load_file(filename)


    def load_file(self, filename:str) -> None:
        """
        Try to load the data of a trip from a given filename.
        Raise a ValueError if the file's extension is not .csv or .json
        """

        # Legacy format
        if filename[-4:] == ".csv":
            self.gps_data      = pd.read_csv(filename)
            self.journey_modes = get_modes_from_filename(filename)
        
        # New format
        elif filename[-5:] == ".json":
            with open(filename, 'r') as json_file:

                data = json.load(json_file)
            
            # Older version
            if type(data["gps"]) == str:
                self.gps_data = pd.read_csv(io.StringIO(data["gps"]))

            # Last version
            else:
                # The format of a record should be 
                # [date:str, longitude:float, latitude:float] but if the first 
                # element isn't a string (it's a mistake) we consider the line
                # has the format [longitude, latitude, date]
                if data["gps"] != [] and type(data["gps"][0][0]) == str:
                    cols = [Journey.time_str, Journey.lon, Journey.lat]
                else:
                    cols = [Journey.lon, Journey.lat, Journey.time_str]

                self.gps_data = pd.DataFrame(data["gps"], columns=cols)
                
            self.journey_modes = data["journey"]

        else:
            raise ValueError(f"Unknow file type : {filename} must be .csv or .json")
        
        # Adding the datetime object calculated from the date (which is a string)
        self.gps_data[Journey.time] = self.gps_data[Journey.time_str].apply(
            lambda date_str: datetime.fromisoformat(date_str)
        )
            

class FileIterator:

    def __init__(self, folder, level=0, show_progress=True):
        """
        folder : the path of the folder where the trip are
        level : If journeys are directly in the folder level is 0 
        (value by default). If journeys are in subfolders put 1.
        No other level is supported because I'm lazy to write a general
        algotithm.
        show_progress : if True print a line showing the status of the 
        operation
        """

        
        if folder[-1] not in ("/", "\\"):
            folder += "/"


        if level == 0:
            self.nb_files = len(os.listdir(folder))

        elif level == 1:
            self.nb_files = 0
            for subfolder in os.listdir(folder):
                self.nb_files += len(os.listdir(folder + subfolder))

        else:
            raise ValueError(f"level with value of {level} is not supported")
        

        self.folder = folder
        self.level = level
        self.show_progress = show_progress
        

    def __iter__(self):

        i = 1
        for file, short_name in self._get_file_iterator():
            
            if self.show_progress:
                progress = f"file : {short_name} \t" + \
                            f"({round(i / self.nb_files * 100, 2)} %)"
                print("\r" + progress, flush=True, end="           ")
            
            yield file

            i += 1

    def _get_file_iterator(self):

        if self.level == 0:
            for file in os.listdir(self.folder):
                yield self.folder + file, file

        else:
            for subfolder in os.listdir(self.folder):
                for file in os.listdir(self.folder + subfolder):

                    short_name = f'{subfolder}/{file}'
                    yield self.folder + short_name, short_name


def get_available_mode_types() -> list:
    """Returns the list of all type of trips a commuter can choose"""

    return ["walk", "bike", "car", "bus", "luas", "dart"]

def get_public_transport_modes() -> list:
    """Return the list of all public transport modes available"""

    return ["bus", "luas", "dart"]

def get_private_transport_modes() -> list:
    """Return the list of all private modes available"""

    return ["walk", "bike", "car"]


def get_modes_from_filename(filename:str) -> list:
    """
    Returns the list of the modes present in the trip associted with 'filename'

    The files are named with this convention to parse them easily:
    trip1_trip2_etc#what-you-want-here.csv

    A trip is just the name of the transport mode when it's walk, bike or car.
    For public transports it has this form mode-line. For example : bus-16A, 
    luas-Red.

    An example of a complete name : walk_bus-4A_car_luas-Green_bike#hello.csv

    """

    COMMENT_SEPARATOR = '#'
    TRIPS_SEPARATOR   = '_'
    LINE_SEPARATOR    = '-'

    filename = filename.split("\\")[-1].split("/")[-1]
    print(filename)
    trips = filename.split(COMMENT_SEPARATOR)[0] \
                    .split(TRIPS_SEPARATOR)

    for i in range(len(trips)):
        trips[i] = trips[i].split(LINE_SEPARATOR)

    return trips


def check_journey_consistency(journey) -> bool:
    """
    Check if a journey is consistent. For example, it cannot contains two 
    successive walk trip.
    """

    # Check if a journey is empty and if it's not too long
    if len(journey) == 0 or len(journey) > 5:
        return False
    
    # Check if there is two consecutive modes. It can only happen for public 
    # transport (e.g. bus) and lines must be different. DART is an exeption
    # since there is only one line.
    for i in range(len(journey) - 1):

        mode      = journey[i  ][0]
        next_mode = journey[i+1][0]

        if mode == next_mode:
            if mode in ("walk", "bike", "car", "dart"):
                return False
            
            else:
                line      = journey[i  ][1]
                next_line = journey[i+1][1]

                if line == next_line:
                    return False
    
    # Check if there is two consecutive private modes
    for i in range(len(journey) - 1):

        mode      = journey[i  ][0]
        next_mode = journey[i+1][0]

        if mode in ("walk", "bike", "car") and \
           next_mode in ("walk", "bike", "car"):
            
            print("Two consecutive private modes are not handled for now")
            return False
        

    return True
        


def gps_distance(lat_1, lon_1, lat_2, lon_2):
    """Return the distance between two gps points in meters"""

    return haversine.haversine(
        (lat_1, lon_1),
        (lat_2, lon_2),
        unit=haversine.Unit.METERS
    )

def calc_speed(df):
    """Returns the speed from the position data"""

    LAT_COL_NAME  = "latitude"
    LON_COL_NAME  = "longitude"
    TIME_COL_NAME = "created"

    old_lat, old_lon, old_date = None, None, None
    speeds = []
    
    for i, rows in df.iterrows():

        lat, lon = rows[LAT_COL_NAME], rows[LON_COL_NAME]
        date = dateutil.parser.parse(rows[TIME_COL_NAME])

        if old_lat is not None:

            distance = gps_distance(old_lat, old_lon, lat, lon)

            delta_time = (date - old_date).total_seconds()

            if delta_time > 0.000001:
                # speed is in km/h
                speeds.append(distance / delta_time * 3.6)
            else:
                speeds.append(0.0)

        old_lat, old_lon, old_date = lat, lon, date

    return speeds

def calc_trip_time(df:pd.DataFrame):
    """
    Return the difference of time in hours between the first and the last 
    point of the dataframe.
    """

    start_time = df.iloc[ 0]["created"]
    end_time   = df.iloc[-1]["created"]

    start_time = dateutil.parser.parse(start_time)
    end_time   = dateutil.parser.parse(end_time)

    return (end_time - start_time).total_seconds() / 3600


def calc_distance(df:pd.DataFrame) -> float:
    """
    Return the distance of a list of point

    df: a dataframe containing data about a trip
    """

    old_lat, old_lon = None, None
    distance = 0.0
    
    for _, rows in df.iterrows():

        lat, lon = rows["latitude"], rows["longitude"]

        if old_lat is not None:
            distance += gps_distance(old_lat, old_lon, lat, lon)

        old_lat, old_lon = lat, lon

    return distance

def calc_distance_by_mode(df, mode_list, detection) -> dict:
    """
    Return the distance travelled for each mode of transport.
    
    df: the data about the trip
    mode_list: the list of mode of transports about the trip
    detection: the list of detected mode of transports
    
    For instance, if mode_list = (("walk", ""), ("bus", "1") ,("walk", "")), 
    the result will have this shape : {"walk": 1045.3, "bus": 5565.2}
    """

    res = {}

    for mode, detected in zip(mode_list, detection):

        mode_name = mode[0]

        if mode_name not in res:
            res[mode_name] = 0

        print("df : ", df)
        print("start, end : ", detected.gps_index_start, detected.gps_index_end)
        res[mode_name] += calc_distance(
            df.iloc[detected.gps_index_start: detected.gps_index_end]
        )

    return res


def get_available_lines(gtfs_data:GtfsData):
    """
    Return a list of all lines found in the 'routes.txt' file
    """

    return gtfs_data.get_routes()["route_short_name"].tolist()


if __name__ == '__main__':

    gtfs_data = GtfsData("GTFS_rail/")

    #print(get_available_lines(gtfs_data))

    
