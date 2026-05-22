class Car:
    def __init__(self, car_id, race_id, driver_id, speed, rpm, throttle, brake, drs, gear, lap, data_time, created_at):
        self.car_id = car_id
        self.race_id = race_id
        self.driver_id = driver_id
        self.speed = speed
        self.rpm = rpm
        self.throttle = throttle
        self.brake = brake
        self.DRS = drs
        self.gear = gear
        self.lap = lap
        self.data_time = data_time
        self.created_at = created_at

    def to_json(self):
        return {
            "car_id": self.car_id,
            "race_id": self.race_id,
            "driver_id": self.driver_id,
            "speed": self.speed,
            "rpm": self.rpm,
            "throttle": self.throttle,
            "brake": self.brake,
            "DRS": self.DRS,
            "gear": self.gear,
            "lap": self.lap,
            "data_time": self.data_time,
            "created_at": self.created_at
        }


class CarPerformance:
    def __init__(self, perf_id, race_id, driver_id, driver_name,
                 max_speed, max_rpm, avg_throttle, avg_brake, drs_time,
                 best_lap_time, total_laps, created_at=None):
        self.perf_id = perf_id
        self.race_id = race_id
        self.driver_id = driver_id
        self.driver_name = driver_name
        self.max_speed = max_speed
        self.max_rpm = max_rpm
        self.avg_throttle = avg_throttle
        self.avg_brake = avg_brake
        self.drs_time = drs_time
        self.best_lap_time = best_lap_time
        self.total_laps = total_laps
        self.created_at = created_at

    def to_json(self):
        return {
            "perf_id": self.perf_id,
            "race_id": self.race_id,
            "driver_id": self.driver_id,
            "driver_name": self.driver_name,
            "max_speed": self.max_speed,
            "max_rpm": self.max_rpm,
            "avg_throttle": self.avg_throttle,
            "avg_brake": self.avg_brake,
            "drs_time": self.drs_time,
            "best_lap_time": self.best_lap_time,
            "total_laps": self.total_laps,
            "created_at": str(self.created_at) if self.created_at else None
        }


class Stint:
    def __init__(self, stint_id, race_id, driver_id, driver_name,
                 stint_number, compound, lap_start, lap_end,
                 tyre_age, is_fresh, created_at=None):
        self.stint_id = stint_id
        self.race_id = race_id
        self.driver_id = driver_id
        self.driver_name = driver_name
        self.stint_number = stint_number
        self.compound = compound
        self.lap_start = lap_start
        self.lap_end = lap_end
        self.tyre_age = tyre_age
        self.is_fresh = is_fresh
        self.created_at = created_at

    def to_json(self):
        return {
            "stint_id": self.stint_id,
            "race_id": self.race_id,
            "driver_id": self.driver_id,
            "driver_name": self.driver_name,
            "stint_number": self.stint_number,
            "compound": self.compound,
            "lap_start": self.lap_start,
            "lap_end": self.lap_end,
            "tyre_age": self.tyre_age,
            "is_fresh": self.is_fresh,
            "laps_in_stint": (self.lap_end - self.lap_start + 1) if self.lap_end and self.lap_start else None,
            "created_at": str(self.created_at) if self.created_at else None
        }