# OrcaSlicer Spoolman Bridge

<p align="center">
  <img src="logo.png" width="200" alt="Spoolman Bridge Logo">
</p>

An OrcaSlicer Python plugin integrating with [Spoolman](https://github.com/Donkie/Spoolman/), a universal self-hosted filament inventory manager.

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Configuration & Usage](#configuration--usage)
- [License](#license)

## Features

- [x] **Universal Spoolman Integration**: Connects to your local or hosted Spoolman API instance.
- [x] **Automatic Presets Synchronization**: Imports active Spoolman spools as custom filament profiles.
- [x] **Duplicated Slicing Profiles**: Automatically duplicates your slicing processes and binds the plugin pipeline to them.
- [x] **Smart Preset Merging**: Modifying settings in the OrcaSlicer UI (retraction, volumetric limits, fan overrides) is preserved and never overwritten by subsequent synchronizations.
- [x] **Onboarding & Unified Setup**: Integrated interactive setup wizard explaining the plugin workflows.
- [x] **API Status Validation**: Validates connections automatically, prompting configuration adjustments if offline.
- [x] **Confirmed Usage Tracking**: Extracts single-filament G-code usage, queues it locally, and records it in Spoolman only after you run **Review Spoolman Usage** and confirm the print.

## How It Works

1. **Spool Filament Presets**: For every active spool in Spoolman, the bridge creates a custom user filament preset formatted as `Vendor FilamentName (#ID) - Spoolman` (e.g. `eSun PLA-Basic White (#2) - Spoolman`).
   ![Filament Preset](docs/filament_preset.png)
   
2. **Duplicated Slicing Profiles**: The bridge copies all your active process presets (slicing profiles) and appends `- SpoolMan` to their names.
   ![Process Preset](docs/process_preset.png)
   
3. **Activation**: Select **both** a synced Spoolman filament preset **and** a synced `- SpoolMan` process preset. Slicing with both active queues usage for review. Multi-filament jobs are skipped because the current parser cannot safely assign each material's weight to a spool.
   ![Print Settings with Plugin](docs/print_settings_with_plugin.png)
   ![Plugin Capabilities](docs/plugin_capabilities.png)

## Installation

Deactivate the cloud-subscribed Spoolman plugin and any older local versions first, so two copies cannot modify the same presets or record the same usage. In OrcaSlicer, open **File > Plugins**, use the split install button's **Install local plugin** option, and select `orcaslicer_plugin_spoolman-1.2.1-py3-none-any.whl`. Activate the new version and restart OrcaSlicer. When upgrading from an earlier wheel, open **Settings & Guide** and enter the Spoolman URL again; settings stored inside the previous wheel's extracted folder are not carried forward automatically.

Version 1.2.1 fixes the user preset path for wheel installations. Earlier wheels could load and connect to Spoolman but report no changes during sync because they looked for presets inside the extracted wheel folder.

## Configuration & Usage

1. **Open Spoolman**: Select the **Spoolman** tab in OrcaSlicer's main window. It provides **Settings & Guide**, **Sync Spoolman Profiles**, and **Review Spoolman Usage** buttons. If the tab is hidden, check **Preferences > General > Plugins > Visible plugin pages** and make sure the Spoolman page capability is enabled in the Plugins window.
2. **Guide & URL Setup**: Open **Settings & Guide** and set your Spoolman server URL. For an Unraid server, enter `http://<UNRAID_IP>:7912` with your server's actual address. The URL stays in a local settings file and is not stored in this repository.
   ![Settings Modal](docs/settings_modal.png)
   
3. **Synchronization**: Select **Sync Spoolman Profiles** in the Spoolman tab to query Spoolman and populate OrcaSlicer's user directory.
   ![Prompt Sync New Profiles](docs/prompt_sync_new_profiles.png)
   
4. **Weight Deduction**: After a successful single-filament print, select **Review Spoolman Usage** in the Spoolman tab. Confirm the displayed spool ID and weight to record consumption, choose No to discard the pending record, or Cancel to leave it for later. If a request times out, verify the roll's remaining weight in Spoolman before clearing the pending record; the plugin will not automatically retry an uncertain deduction.

This fork uses OrcaSlicer's `create_window(..., style=WINDOW_MODAL, on_submit=...)` API in place of the unavailable `show_dialog()` call. Profile synchronization no longer deletes existing Spoolman custom fields. The upstream project and its original authors retain credit under the MIT license.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
