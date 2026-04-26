from locust import HttpUser, task, between

class GatewayUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def check_health(self):
        self.client.get("/health")

    @task
    def send_message(self):
        self.client.post("/message", json={"text": "Hello"})
