# Fotofeld for Home Assistant

> **Work in progress — not tested on a real Home Assistant yet.** Don't install it unless you are helping test it.

Connects Home Assistant to [Fotofeld](https://github.com/Sanfeld/photo-organizer), the family photo library on a Windows computer. You get:

- **Photos on your dashboards and panels:** *On this day* (the same day in earlier years), *Random*, *Latest*, one photo entity per person you've named in Fotofeld Vision, and a *Photo frame* that automations can point at anyone or anything.
- **The library at a glance:** how many files there are, what is happening right now, the last sort, the last USB import, *Not sure* and duplicate counts.
- **Phones:** when each phone last backed up, and a warning when one hasn't for a few days.
- **The disk:** free space, Windows' health status, uncorrected read errors and temperature, with a *Disk problem* sensor to alert on.
- **Fotofeld Vision:** start an analysis, follow its progress, and see how many faces are waiting for a name.
- **Control:** pause and resume the Fotofeld service, and start Vision.
- **Events** for automations: USB import started/finished, disk problem, analysis finished, new faces, phone overdue, paused/resumed.

Swedish and English.

## Requirements

- Fotofeld **1.1** or newer running as a service (section 5 of the Fotofeld window, *Install*). The service listens on port 8765, and its installer opens that port for the local network.
- Fotofeld Vision for the per-person, subject and *On this day* photos. Without Vision, *Random* and *Latest* still work.

## Install with HACS

1. In HACS, open the menu (⋮) → **Custom repositories**. Add `https://github.com/Sanfeld/ha-fotofeld` with type **Integration**.
2. Search HACS for **Fotofeld**, open it and click **Download**. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Fotofeld**. Enter the Fotofeld computer's address (for example `192.168.1.231`), port `8765`, and the **pairing code** shown in section 5 of the Fotofeld window (the same code the phone app uses).

**Configure** on the integration sets how often the photos change (0 = only when asked), their size, and after how many days a phone counts as overdue.

## Entities

Names start with `fotofeld_<computer name>_`.

| Entity | What it shows |
|---|---|
| `image.…_on_this_day` | A photo taken on this day in an earlier year (or within three days of it). Attributes: `date`, `years_ago`, `people`, `subjects`. Changes at midnight too. |
| `image.…_random_photo`, `image.…_latest_photo` | A random photo; the newest one. |
| `image.…_photo_of_<name>` | One per person named in Fotofeld Vision. |
| `image.…_photo_frame` | Random to start with; `fotofeld.next_photo` with a mode/name changes what it shows. |
| `sensor.…_activity` | idle, busy, paused, or what is running (for example `Copying 1200/5000`). |
| `sensor.…_files_in_library`, `…_sorted_files`, `…_not_sure`, `…_duplicates`, `…_last_filed` | The library. |
| `sensor.…_usb_import`, `…_last_usb_import`, `…_last_sort` | USB imports and sorts, with counts and log path as attributes. |
| `sensor.…_<phone>_last_backup`, `binary_sensor.…_<phone>_backup_overdue`, `binary_sensor.…_phone_backup_overdue` | Each phone folder, and whether any phone is overdue. |
| `sensor.…_disk_free`, `…_disk_used`, `…_disk_health`, `…_disk_read_errors`, `…_disk_temperature`, `binary_sensor.…_disk_problem` | The disk the Fotofeld folder is on. |
| `binary_sensor.…_analyzing`, `sensor.…_analysis_progress`, `…_last_analysis`, `…_faces_to_name`, `…_named_people` | Fotofeld Vision. |
| `binary_sensor.…_busy`, `switch.…_paused` | The service. |
| `image.…_duplicate_check_original`, `image.…_duplicate_check_duplicate`, `button.…_next_original` / `…_previous_original` / `…_random_original` / `…_next_duplicate` / `…_previous_duplicate`, `text.…_duplicate_check_filter` | The duplicates viewer: an original and one of its duplicates side by side, to spot-check what Fotofeld treated as the same picture. Needs Fotofeld 1.2. |
| `select.…_photo_frame_shows` | What the Photo frame shows: Random, On this day, Latest, `Person: <name>` or `Subject: <name>`. |
| `button.…_analyze_pictures`, `button.…_show_new_photos` | Start Vision; a new photo on every photo entity. |
| `event.…_fotofeld` | The last thing that happened. |

## Actions

| Action | |
|---|---|
| `fotofeld.next_photo` | On image entities: a new photo now. Optional `mode` (`random`, `onthisday`, `latest`, `person`, `subject`) and `name` change what that entity shows. |
| `fotofeld.find_photo` | Returns a photo's `date`, `yearsAgo`, `people` and `subjects`, for scripts and notifications. |
| `fotofeld.analyze` | Runs Fotofeld Vision on new pictures. |
| `fotofeld.pause`, `fotofeld.resume` | No USB, inbox or phone work while paused. Phones retry later. |

## Events

Every event is fired as `fotofeld_event` with `type` and its details, and shown on the event entity:

| `type` | Details |
|---|---|
| `service_started` | `version` |
| `usb_started` | `drive`, `name` |
| `usb_finished` | `drive`, `name`, `result` (`done`, `removed`, `incomplete`, `failed`), `copied`, `alreadyThere`, `errors` |
| `disk_problem` | `drive`, `model`, `health`, `readErrors` |
| `vision_finished` | `ok`, `error`, `pictures`, `unnamedFaceGroups` |
| `new_faces` | `unnamedFaceGroups` |
| `phone_overdue` | `phone`, `lastBackup` |
| `paused`, `resumed` | |

See [`examples/automations.yaml`](examples/automations.yaml) for USB, disk, phone and nightly-analysis automations, [`examples/fotofeld-dashboard.yaml`](examples/fotofeld-dashboard.yaml) for a full Fotofeld dashboard (Overview, Photos, Duplicates, Phones, Imports, Vision, Disk; built-in cards only), and [`examples/dashboard.yaml`](examples/dashboard.yaml) for a single Photos view.

## Privacy

Everything stays on your network: Home Assistant talks to the Fotofeld computer directly, with the pairing code. Photos are only fetched when a photo entity changes, at the size you choose.
