import unittest
from unittest.mock import patch, MagicMock
from typing import Any, Dict

from voice_assistant.apis.calendar import  RestCalendarClient


def make_response(status: int, json_body: Dict[str, Any]) -> MagicMock:
    """Helper to build a mock requests.Response-like object."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_body
    resp.text = str(json_body)
    return resp


class TestRestCalendarClient(unittest.TestCase):
    def setUp(self) -> None:
        self.client = RestCalendarClient()

    @patch("requests.post")
    def test_create_event_success(self, mock_post):
        payload = {
            "title": "Meeting with team",
            "description": "Discuss project",
            "start_time": "2025-11-03T09:00",
            "end_time": "2025-11-03T10:00",
            "location": "Room 12",
        }
        entry = {"id": 1, **payload}
        mock_post.return_value = make_response(200, {"entry": entry})

        result = self.client.create_event(**payload)

        self.assertEqual(result, entry)
        mock_post.assert_called_once_with(self.client.base_url, json=payload)

    @patch("requests.post")
    def test_create_event_error(self, mock_post):
        mock_post.return_value = make_response(400, {"error": "bad request"})
        with self.assertRaises(Exception) as ctx:
            self.client.create_event(
                title="x", description="y",
                start_time="2025-11-03T09:00", end_time="2025-11-03T10:00",
                location="Room 12"
            )
        self.assertIn("API error 400", str(ctx.exception))

    @patch("requests.get")
    def test_get_event_success(self, mock_get):
        entry = {"id": 5, "title": "Standup"}
        mock_get.return_value = make_response(200, {"entry": entry})

        result = self.client.get_event(5)

        self.assertEqual(result, entry)
        mock_get.assert_called_once_with(f"{self.client.base_url}?id=5")

    @patch("requests.get")
    def test_get_event_error(self, mock_get):
        mock_get.return_value = make_response(404, {"error": "not found"})
        with self.assertRaises(Exception) as ctx:
            self.client.get_event(999)
        self.assertIn("API error 404", str(ctx.exception))

    @patch("requests.put")
    def test_update_event_partial_success(self, mock_put):
        event_id = 3
        update_payload = {"title": "Updated title", "location": "Room 15"}
        entry = {"id": event_id, **update_payload}
        mock_put.return_value = make_response(200, {"entry": entry})

        result = self.client.update_event(event_id=event_id, **update_payload)

        self.assertEqual(result, entry)
        mock_put.assert_called_once_with(
            f"{self.client.base_url}?id={event_id}",
            json=update_payload
        )

    @patch("requests.put")
    def test_update_event_error(self, mock_put):
        mock_put.return_value = make_response(500, {"error": "server"})
        with self.assertRaises(Exception) as ctx:
            self.client.update_event(event_id=1, title="Oops")
        self.assertIn("API error 500", str(ctx.exception))


    @patch("requests.delete")
    def test_delete_event_not_deleted_message(self, mock_delete):
        event_id = 8
        body = {"message": "not-deleted"}
        mock_delete.return_value = make_response(200, body)

        with self.assertRaises(Exception) as ctx:
            self.client.delete_event(event_id)
        self.assertIn("Could not delete the event", str(ctx.exception))

    @patch("requests.delete")
    def test_delete_event_error(self, mock_delete):
        mock_delete.return_value = make_response(403, {"error": "forbidden"})
        with self.assertRaises(Exception) as ctx:
            self.client.delete_event(1)
        self.assertIn("API error 403", str(ctx.exception))

    @patch("requests.get")
    def test_list_events_success(self, mock_get):
        entries = [{"id": 1}, {"id": 2}]
        mock_get.return_value = make_response(200, {"entries": entries})

        result = self.client.list_events()

        self.assertEqual(result, entries)
        mock_get.assert_called_once_with(self.client.base_url)

    @patch("requests.get")
    def test_list_events_error(self, mock_get):
        mock_get.return_value = make_response(503, {"error": "unavailable"})
        with self.assertRaises(Exception) as ctx:
            self.client.list_events()
        self.assertIn("API error 503", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
