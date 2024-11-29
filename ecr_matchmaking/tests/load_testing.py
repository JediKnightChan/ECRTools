import uuid

from locust import HttpUser, task, between


class WebAppUser(HttpUser):
    # Wait time between tasks (simulates user think time)
    wait_time = between(5, 10)

    def on_start(self):
        """
        Called when a simulated user is spawned. Assigns a unique player_id to each user.
        """
        self.player_id = str(uuid.uuid4())

    # Define tasks
    @task(10)  # Task weight: accessed more frequently
    def reenter_matchmaking_queue(self):
        """
        Enter queue
        """
        data = {
            "player_id": self.player_id,
            "pool_id": "prod",
            "desired_match": "carmine_group"
        }
        self.client.post("/reenter_matchmaking_queue", json=data)

    @task(1)
    def leave_matchmaking_queue(self):
        """
        Exit queue
        """
        data = {
            "player_id": self.player_id
        }
        self.client.post("/leave_matchmaking_queue", json=data)
