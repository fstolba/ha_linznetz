## Example automation for daily inserts

This example uses [emcniece/ha_imap_attachment](https://github.com/emcniece/ha_imap_attachment/) to download the attachments. You can install this component manually or as an HACS custom repository.

0. Optional: Before setting up the daily automation you can bulk import all your available previous QH values. Download them from linznetz.at as a csv file, copy this file to your HA installation and call the `linznetz.import_report` service from the HA developer tools page. This integrations tries to re-calculate and update the statistics when missing values are inserted afterwards but it's safer to insert them chronologically.
1. Install `ha_imap_attachment` and follow the steps to create a new folder for the attachments on your HA installation (we use `/config/attachments` here).
2. Lookup the IMAP configurations for your mail provider (example below uses Outlook). For Gmail you will have to set an App Password on your Google account and enable Multi-Factor Authentication (see [core IMAP docs](https://www.home-assistant.io/integrations/imap/#gmail-with-app-password)).
3. Optional: Login to your mail provider and create a new folder for the LINZ NETZ reports, e.g. `VDI`. If you don't want to use a new folder you have to use the folder `INBOX` in your configuration but it will be difficult to filter this way.
4. **IMPORTANT**: Since the reports are sent with SMIME encryption `ha_imap_attachment` downloads the encrypted mail instead of the attachments. To solve this problem you have to configure some rules for your inbox as a workaround: The easiest way is to forward the daily reports to yourself (or another mail address), this will remove the encryption (tested with Outlook.com). Example rules:
```
1. Mails with titles containing "Tagesbericht Viertelstundenverbrauch" from "vdi@linznetz.at" forward to <my mail address> and delete original mail.
2. Mails with titles containing "Tagesbericht Viertelstundenverbrauch" from <my mail address> move to folder "VDI".
```
5. Add the configs from the `configuration.yaml` example below to your configurations.
6. Restart Home-Assistant. You can test the configuration with forwarding a daily report to yourself. You should see a `sensor.linz_netz_attachments` (based on the sensor name in the configuration) entity with the path to a csv file now (this can take some minutes).
7. Create an automation like the `automation-example.yaml` below (as a file or with the UI; you can copy-paste this as-is).

### Some known problems

1. It can happen that the `ha_imap_attachment` loses connection to the IMAP server and does not re-connect in time when the daily report arrives. When this happens you can simply forward the e-mail report to yourself again and it should be downloaded and inserted. Beware that the IMAP integration may need some minutes until it detects the e-mail. Another way would be to download and import the report manually.
2. The same problem can happen if your HA instance is down (e.g. during an update or power outage) at this time. You can use the same fix mentioned above.
3. Although they claim to send you the report until 12:00 it can be later too. Normally you will get your report at the same time as the day before +/- 5 minutes.
4. It happens that LINZ NETZ does not send you a report on some days (I don't know why, maybe the SmartMeter does not send the data to them as you cannot see the values online either). Normally you will get two mails on the next day and this automation inserts them without a problem.

### configuration.yaml

```yaml
homeassistant:
  allowlist_external_dirs:
    - "/config/attachments"

sensor:
  - platform: imap_attachment
    name: LINZ NETZ Attachments
    server: outlook.office365.com
    port: 993
    folder: VDI
    senders:
        - !secret outlook_mail
    username: !secret outlook_mail
    password: !secret outlook_password
    storage_path: /config/attachments
    value_template: "{{ ( attachment_paths | select('search', '.csv')) | first | default('unavailable') }}"
```

### automation-example.yaml
```yaml
alias: Import Linz Netz Email Reports
description: ""
trigger:
  - platform: state
    entity_id:
      - sensor.linz_netz_attachments
condition:
  - condition: not
    conditions:
      - condition: state
        entity_id: sensor.linz_netz_attachments
        state: unknown
      - condition: state
        entity_id: sensor.linz_netz_attachments
        state: unavailable
action:
  - service: linznetz.import_report
    data:
      entity_id: sensor.smartmeter_energy
      path: "{{ states('sensor.linz_netz_attachments') }}"
mode: single
```
