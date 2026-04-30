#!/bin/bash
# Must be run on a Macinotosh device (MacOS) with pyinstaller installed. This script will create a DMG installer for the BrewStore application.
mkdir BrewStore_DMG
pyinstaller --noconsole --onefile --windowed --name "BrewStore" brewstore.py
mv dist/BrewStore.app BrewStore_DMG
ln -s /Applications ./BrewStore_DMG/Applications
hdiutil create -volname "BrewStore Installer" -srcfolder ./BrewStore_DMG -ov -format UDZO BrewStore.dmg