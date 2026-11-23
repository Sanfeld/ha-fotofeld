"""Constants for Fotofeld."""

DOMAIN = "fotofeld"
DEFAULT_PORT = 8765

CONF_CODE = "code"
CONF_OVERDUE_DAYS = "overdue_days"
CONF_PHOTO_MINUTES = "photo_minutes"
CONF_PHOTO_SIZE = "photo_size"

DEFAULT_OVERDUE_DAYS = 3
DEFAULT_PHOTO_MINUTES = 60
DEFAULT_PHOTO_SIZE = 1280

SCAN_SECONDS = 30

# Fired on the event bus as "fotofeld_event" and shown on the Fotofeld event entity.
EVENT_BUS = "fotofeld_event"
EVENT_TYPES = [
    "service_started",
    "usb_started",
    "usb_finished",
    "disk_problem",
    "vision_finished",
    "new_faces",
    "phone_overdue",
    "paused",
    "resumed",
]

PHOTO_MODES = ["random", "onthisday", "latest", "person", "subject"]
