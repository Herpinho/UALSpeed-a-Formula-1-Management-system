class Race:
    def __init__(self, race_id, name, circuit, country, date, total_laps, status):
        self.race_id = race_id
        self.name = name
        self.circuit = circuit
        self.country = country
        self.date = date
        self.total_laps = total_laps
        self.status = status  # scheduled, live, completed

    def to_json(self):
        return {
            "race_id": self.race_id,
            "name": self.name,
            "circuit": self.circuit,
            "country": self.country,
            "date": str(self.date) if self.date else None,
            "total_laps": self.total_laps,
            "status": self.status
        }


class RaceResult:
    def __init__(self, result_id, race_id, driver_id, driver_name, team, 
                 position, points, fastest_lap, total_time, status):
        self.result_id = result_id
        self.race_id = race_id
        self.driver_id = driver_id
        self.driver_name = driver_name
        self.team = team
        self.position = position
        self.points = points
        self.fastest_lap = fastest_lap
        self.total_time = total_time
        self.status = status  # finished, dnf, dns, dsq

    def to_json(self):
        return {
            "result_id": self.result_id,
            "race_id": self.race_id,
            "driver_id": self.driver_id,
            "driver_name": self.driver_name,
            "team": self.team,
            "position": self.position,
            "points": self.points,
            "fastest_lap": self.fastest_lap,
            "total_time": self.total_time,
            "status": self.status
        }


class Lap:
    def __init__(self, lap_id, race_id, driver_id, driver_name, lap_number, 
                 lap_time, sector1, sector2, sector3, position):
        self.lap_id = lap_id
        self.race_id = race_id
        self.driver_id = driver_id
        self.driver_name = driver_name
        self.lap_number = lap_number
        self.lap_time = lap_time
        self.sector1 = sector1
        self.sector2 = sector2
        self.sector3 = sector3
        self.position = position

    def to_json(self):
        return {
            "lap_id": self.lap_id,
            "race_id": self.race_id,
            "driver_id": self.driver_id,
            "driver_name": self.driver_name,
            "lap_number": self.lap_number,
            "lap_time": self.lap_time,
            "sector1": self.sector1,
            "sector2": self.sector2,
            "sector3": self.sector3,
            "position": self.position
        }


class Driver:
    def __init__(self, driver_id, name, nationality, number, team_id, team_name=None):
        self.driver_id = driver_id
        self.name = name
        self.nationality = nationality
        self.number = number
        self.team_id = team_id
        self.team_name = team_name  # join com a tabela teams

    def to_json(self):
        return {
            "driver_id": self.driver_id,
            "name": self.name,
            "nationality": self.nationality,
            "number": self.number,
            "team_id": self.team_id,
            "team_name": self.team_name
        }


class Team:
    def __init__(self, team_id, name, nationality, car_model):
        self.team_id = team_id
        self.name = name
        self.nationality = nationality
        self.car_model = car_model

    def to_json(self):
        return {
            "team_id": self.team_id,
            "name": self.name,
            "nationality": self.nationality,
            "car_model": self.car_model
        }


class Standing:
    def __init__(self, standing_id, driver_id, driver_name, team, position, 
                 points, wins, podiums, fastest_laps):
        self.standing_id = standing_id
        self.driver_id = driver_id
        self.driver_name = driver_name
        self.team = team
        self.position = position
        self.points = points
        self.wins = wins
        self.podiums = podiums
        self.fastest_laps = fastest_laps

    def to_json(self):
        return {
            "standing_id": self.standing_id,
            "driver_id": self.driver_id,
            "driver_name": self.driver_name,
            "team": self.team,
            "position": self.position,
            "points": self.points,
            "wins": self.wins,
            "podiums": self.podiums,
            "fastest_laps": self.fastest_laps
        }