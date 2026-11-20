# Removes the leftovers of Dropbox marked "safe" on this page. Nothing else.

# 1. Stop Dropbox's background helpers
launchctl bootout gui/$(id -u) "$HOME/Library/LaunchAgents/com.dropbox.dropboxmacupdate.agent.plist" 2>/dev/null
launchctl bootout gui/$(id -u) "$HOME/Library/LaunchAgents/com.dropbox.dropboxmacupdate.xpcservice.plist" 2>/dev/null
launchctl bootout gui/$(id -u) "$HOME/Library/LaunchAgents/com.dropbox.DropboxUpdater.wake.plist" 2>/dev/null

# 2. Delete the leftover files and folders
rm -rf \
  "$HOME/.dropbox" \
  "$HOME/Library/Application Scripts/com.getdropbox.dropbox.fileprovider" \
  "$HOME/Library/Application Scripts/com.getdropbox.dropbox.garcon" \
  "$HOME/Library/Application Scripts/com.getdropbox.dropbox.TransferExtension" \
  "$HOME/Library/Application Scripts/G7HH3F8CAK.com.getdropbox.dropbox.sync" \
  "$HOME/Library/Application Support/Dropbox" \
  "$HOME/Library/Containers/com.getdropbox.dropbox.fileprovider" \
  "$HOME/Library/Containers/com.getdropbox.dropbox.garcon" \
  "$HOME/Library/Containers/com.getdropbox.dropbox.TransferExtension" \
  "$HOME/Library/Group Containers/G7HH3F8CAK.com.getdropbox.dropbox.sync" \
  "$HOME/Library/LaunchAgents/com.dropbox.dropboxmacupdate.agent.plist" \
  "$HOME/Library/LaunchAgents/com.dropbox.dropboxmacupdate.xpcservice.plist" \
  "$HOME/Library/LaunchAgents/com.dropbox.DropboxUpdater.wake.plist" \
  "$HOME/Library/Preferences/com.dropbox.DropboxMacUpdate.plist" \
  "$HOME/Library/Preferences/com.getdropbox.dropbox.plist"