class Car:
    def __init__(self,car_id,race_id,driver_id,speed,rpm,throttle,brake,DRS,gear,lap,data_time,created_at):
        self.car_id = car_id
        self.race_id = race_id
        self.driver_id = driver_id
        self.speed = speed # 0(stopped) - 500
        self.rpm = rpm # 0(off) - 22000
        self.throttle = throttle # 0 - 100%
        self.brake = brake # 0 - 100%
        self.DRS = DRS # True or False
        self.gear = gear # -1(R) - 0(N) - 8
        self.lap = lap # 1 - wtv
        self.data_time = data_time #race's relative time at which the data was read
        self.created_at = created_at #actual real life time of data creation
    
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