# LINZ NETZ Importer for Home-Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

_Component to integrate with [ha_linznetz][ha_linznetz]._

**This component will set up the following platforms.**

Platform | Description
-- | --
`sensor` | Placeholder to import statistics by the service.

## Installation

### Supported Versions

The current code was adapted and tested with the following required versions. The integration might work on newer versions, however internal breaking changes introduced by Home-Assistant could break the integration. Please update with caution and open an issue if anything breaks. As a workaround, you can bulk import all your missing reports manually as soon as a fix for this integration is available.

Component | Min. Required Version
-|-
Home-Assistant | 2026.8.1
HACS | 2.0.5

### HACS (Custom Repository)

1. Navigate to `HACS` on your Home-Assistant dashboard.
2. Select `Integrations`.
3. Click on the menu in the top right corner and choose `Custom Repositories`.
4. Insert this repo's https URL (currently https://github.com/fstolba/ha_linznetz) for repository and select category `integration`.
5. Search for `LINZ NETZ` in the integration tab.
6. Click on the integration and install it with the button on the bottom right corner.
7. Restart Home-Assistant as prompted.
8. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "LINZ NETZ".


### Manual

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `linznetz`.
4. Download _all_ the files from the `custom_components/linznetz/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant.
7. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "LINZ NETZ".

Using your HA configuration directory (folder) as a starting point you should now also have this:

```text
custom_components/linznetz/translations/en.json
custom_components/linznetz/__init__.py
custom_components/linznetz/config_flow.py
custom_components/linznetz/const.py
custom_components/linznetz/manifest.json
custom_components/linznetz/sensor.py
custom_components/linznetz/services.yaml
```

## Configurations with the UI

**To use this integration you need a free account at https://www.linznetz.at and enable the quarter-hour(QH) analysis ("Viertelstundenauswertung"). Then it will take 1-2 days until your SmartMeter transfers the QH data to LINZ NETZ.** Please make sure you have a LINZ NETZ account since *LINZ AG Plus24* does not support QH E-Mail reports! (You can have both accounts if you want to.) You can check on the LINZ NETZ services page > "Verbrauchsdateninformation"/"Verbräuche anzeigen" if your SmartMeter supports QH analysis and if your data is already transmitted to LINZ NETZ.

During the configuration you need to provide:

1. **Meter Point Number** (required): The 33 characters long "Zählerpunktnummer" you can find on https://www.linznetz.at > "Meine Verbräuche" > "Verbräuche anzeigen". This number is used as the unique ID. If you don't want to use your real number (e.g. for testing) just use `AT0000000000000000000000000000000` but please make sure you need another number if you need a second instance of this integration!
2. **Name** (optional): A custom name to identify different SmartMeters. The default name is "SmartMeter".
3. **LinzNetz Username** (optional): Your LinzNetz Serviceportal username (e-mail address). If provided together with the password, the integration will **automatically fetch** your consumption data every 6 hours.
4. **LinzNetz Password** (optional): Your LinzNetz Serviceportal password.

### Automatic Data Fetching

As of August 2026, the Automatic Data Fetching feature is broken. You will need to use one of the other ways to import your data. 
The relevant code paths were left untouched during the latest round of modifications.

### Webhook receiver

Each device will register a Webhook Endpoint, yielding one endpoint per Zählerpunktnummer. This Webhook will accept a file attachment as formdata and run the import routine on this file.
This will be useful if you have some sort of Email processing already in place, e.g. via Paperless-ngx.

To retrieve the Webhook URL, either check the Integration's logs or the Energy Sensor's attributes.

### Manual CSV Import

You can still use the manual `linznetz.import_report` service to import CSV files. This is useful for:
- Bulk importing historical data
- If you prefer not to store your credentials
- As a fallback if the automatic fetch encounters issues

This will create a `sensor.smartmeter_energy` entity which you can use to import the QH reports to.

After the import you can use the `sensor.smartmeter_energy` entity on the energy dashboard as a "grid consumption".

## Troubleshooting

Although this integration provides some logic to re-calculate the energy value when missing values are added afterwards (and not chronologically) it may happen that the values are corrupted at some point. The easiest way to fix this is to export a new bulk QH report from LINZ NETZ and import this report with the service to update all the values.

## Integrations

See [INTEGRATIONS.md](./INTEGRATIONS.md) for example setups.

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

## Credits

This project uses the [integration_blueprint](https://github.com/custom-components/integration_blueprint) template and is inspired by the usage of the `async_add_external_statistics` recorder function that is used by the [tibber](https://github.com/home-assistant/core/tree/dev/homeassistant/components/tibber) integration.

***

[ha_linznetz]: https://github.com/DarkC35/ha_linznetz
[commits-shield]: https://img.shields.io/github/commit-activity/y/DarkC35/ha_linznetz.svg?style=for-the-badge
[commits]: https://github.com/DarkC35/ha_linznetz/commits/master
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/DarkC35/ha_linznetz.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-DarkC35-red.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/DarkC35/ha_linznetz.svg?style=for-the-badge
[releases]: https://github.com/DarkC35/ha_linznetz/releases
