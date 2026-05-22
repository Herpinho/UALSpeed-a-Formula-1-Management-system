class Service:
    def __init__(self, service_id, name, url, created_at=None):
        self.service_id = service_id
        self.name = name
        self.url = url
        self.created_at = created_at

    def to_json(self):
        return {
            "service_id": self.service_id,
            "name": self.name,
            "url": self.url
        }


class ServiceCheck:
    def __init__(self, check_id, service_id, service_name, status,
                 latency_ms, status_code, error_msg, checked_at):
        self.check_id = check_id
        self.service_id = service_id
        self.service_name = service_name
        self.status = status        # online, offline, degraded
        self.latency_ms = latency_ms
        self.status_code = status_code
        self.error_msg = error_msg
        self.checked_at = checked_at

    def to_json(self):
        return {
            "check_id": self.check_id,
            "service_id": self.service_id,
            "service_name": self.service_name,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "status_code": self.status_code,
            "error_msg": self.error_msg,
            "checked_at": str(self.checked_at) if self.checked_at else None
        }