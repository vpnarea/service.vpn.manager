#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#    Copyright (C) 2016 Zomboided
#
#    Connection script called by the VPN Manager for OpenVPN settings screen
#    to validate a connection to a VPN provider.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#    This module assists with the import of a user defined VPN provider

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import os
import time
import glob
from libs.utility import debugTrace, errorTrace, infoTrace, newPrint
from libs.vpnproviders import getUserDataPathWrapper, removeGeneratedFiles, cleanPassFiles
from libs.platform import getUserDataPath, getPlatform, platforms, getSeparator, getImportLogPath
from libs.logbox import popupImportLog

# Delete any existing files
def clearUserData():
    debugTrace("Deleting contents of userdata UserDefined directory")
    # Deleting everything here, but not deleting 'DEFAULT.txt' as 
    # any existing user and password info will get deleted
    path = getUserDataPath("UserDefined" + "/*.*")
    files = glob.glob(path)
    try:
        for file in files:
            if not file.endswith("DEFAULT.txt") and xbmcvfs.exists(file): 
                debugTrace("Deleting " + file)
                xbmcvfs.delete(file)
    except Exception as e:
        errorTrace("import.py", "Couldn't clear the UserDefined directory")
        errorTrace("import.py", str(e))
        return False
    return True

    
def getSeparatorOutput():
    if getPlatform() == platforms.WINDOWS:
        # Need to double escape Windows as we output this as another slash gets striped as it gets read back in again
        return "\\\\"
    else:
        return "/"
    
    
addon = xbmcaddon.Addon("service.vpn.manager")
addon_name = addon.getAddonInfo("name")

debugTrace("Entered import.py")

errorMessage = ""
success = False
cancel = False

xbmcgui.Dialog().ok(addon_name, "The User Defined import wizard helps you set up a VPN provider that's not supported.  It may not work without additional user intervention.  You should review the import log and subsequent VPN logs to debug any problems.")

# Warn the user that files will be deleted and kittens will be harmed
if xbmcgui.Dialog().yesno(addon_name, "Any existing User Defined settings and files will be deleted. Do you want to continue?", "", ""):
    cleanPassFiles()
    removeGeneratedFiles()
    success = clearUserData()
    addon.setSetting("vpn_provider", "User Defined")
    if not success: errorMessage = "Could not clear the UserDefined directory. Check the log."
else:
    success = False
    errorMessage = "Import wizard has not been run, no settings or files have been changed."

# Get the list of files to be used
if success:
    if xbmcgui.Dialog().yesno(addon_name, "Select ALL files needed to connect to the VPN provider, including .ovpn, .key and .crt files.  Select a directory (sub directories are ignored) or select multiple files within a directory?.", "", "", "Directory", "Files"):
        directory_input = False
        files = xbmcgui.Dialog().browse(1, "Select all VPN provider files", "files", "", False, False, "c:\\", True)
    else:
        directory_input = True
        dname = xbmcgui.Dialog().browse(0, "Select a directory containing VPN provider files", "files", "", False, False, "c:\\", False)
        files = glob.glob(dname + getSeparator() + "*.*")
        
    # Separate the selected files into ovpn files and other files
    ovpn_files = []
    other_files = []
    for name in files:
        newPrint("name is " + name)
        if name.endswith(".ovpn"):
            ovpn_files.append(name)
        else:
            other_files.append(name)
    if len(ovpn_files) == 0:
        success = False
        errorMessage = "No .ovpn files found.  You must provide at least one .ovpn file."
        
# Copy and modify the ovpn files
if success:
    
    # Create some logs to write out later
    summary = []
    detail = []
   
    summary.append("Importing selected files to userdata directory, " + getUserDataPath("UserDefined/") + "\n")
    summary.append("at " + time.strftime('%Y-%m-%d %H:%M:%S') + "\n")
    detail.append("\n=== Import details ===\n\n")
    
    update = False
    rename = False
    if xbmcgui.Dialog().yesno(addon_name, "Update the .ovpn files to best guess values and determine the best User Defined provider settings (recommended)?", "", ""):
        update = True
        detail.append("Updating the .ovpn files to best guess settings\n")
    if xbmcgui.Dialog().yesno(addon_name, "Rename the .ovpn files to indicate either a UDP or TCP connection type to allow filtering of connections?", "", ""):
        rename = True
        detail.append("Files will be renamed to indicate UDP or TCP\n")        
        
    # Display dialog to show progress of copying files
    dialog_step = 100/(len(ovpn_files) + len(other_files))
    progress = xbmcgui.DialogProgress()
    progress_title = "Copying User Defined files."
    progress.create(addon_name,progress_title) 
    prog_step = 0
    xbmc.sleep(500)
    try:
        other_files_count = []
        for fname in other_files:
            path, dest_name = os.path.split(fname)
            dest_name = getUserDataPath("UserDefined/" + dest_name)
            # Report file being copied, then do it
            progress_message = "Copying " + fname
            progress.update(prog_step, progress_title, progress_message)
            xbmc.sleep(100)
            prog_step += dialog_step
            infoTrace("import.py", "Copying " + fname + " to " + dest_name)
            detail.append("Copying " + fname + " to " + dest_name + "\n")
            xbmcvfs.copy(fname, dest_name)
            other_files_count.append(0)
            if progress.iscanceled():
                cancel = True
                break
        auth_count = 0
        auth_found = 0
        cert_count = 0
        cert_found = 0
        multiple_certs = False
        last_cert_found = ""
        ecert_count = 0
        key_count = 0
        key_found = 0
        multiple_keys = False
        last_key_found = ""
        ekey_count = 0
        if not cancel:
            for oname in ovpn_files:
                path, dest_name = os.path.split(oname)
                dest_name = getUserDataPath("UserDefined/" + dest_name)

                # Report file being copied, then do it
                progress_message = "Copying " + oname
                progress.update(prog_step, progress_title, progress_message)
                xbmc.sleep(100)
                prog_step += dialog_step            
                if update:
                    auth = False
                    # Copy the ovpn file line by line and update anything that looks like it needs it
                    infoTrace("import.py", "Copying and updating " + oname + " to " + dest_name)
                    detail.append("Copying and updating " + oname + " to " + dest_name + "\n")
                    source_file = open(oname, 'r')
                    source = source_file.readlines()
                    source_file.close()
                    dest_file = open(dest_name, 'w')
                    proto = "UDP"
                    for line in source:
                        line = line.strip(' \t\n\r')
                        old_line = line
                        i = 0
                        # Look for each non ovpn file uploaded and update it to make sure the path is good
                        for fname in other_files:
                            path, name = os.path.split(fname)
                            if not line.startswith("#"):
                                params = line.split()
                                if len(params) == 2:
                                    # Remove the separator in order to get any fully qualified filename as space delimited
                                    params[1].replace(getSeparator(), " ")
                                    # Add in a leading space for unqualified filenames
                                    params[1] = " " + params[1]
                                    if params[1].endswith(" " + name):
                                        old_line = line
                                        line = params[0] + " " + "#PATH" + getSeparatorOutput() + name
                                        detail.append("  Found " + name + ", old line was : " + old_line + "\n")
                                        detail.append("  New line is " + line + "\n")
                                        other_files_count[i] += 1
                                        if line.startswith("auth-user-pass"):
                                            auth_found += 1
                                            auth = True
                                        if line.startswith("cert "):
                                            cert_found += 1
                                        if line.startswith("key "):
                                            key_found += 1
                            i += 1
                        # Do some tag counting to determine authentication methods to use
                        if not line.startswith("#"):
                            if line.startswith("auth-user-pass"):
                                auth_count += 1
                                if not auth: line = "auth-user-pass #PATH" + getSeparatorOutput() + " pass.txt"
                            if line.startswith("cert "):
                                cert_count += 1
                                if not last_cert_found == old_line:
                                    if not last_cert_found == "":
                                        multiple_certs = True
                                    last_cert_found = old_line
                            if line.startswith("key "):
                                key_count += 1
                                if not last_key_found == old_line:
                                    if not last_key_found == "":
                                        multiple_keys = True
                                    last_key_found = old_line
                            if line.startswith("proto "):
                                if "tcp" in (line.lower()): proto = "TCP"
                            if line.startswith("<cert>"):
                                ecert_count += 1
                            if line.startswith("<key>"):
                                ekey_count += 1
                        dest_file.write(line+"\n")
                    dest_file.close()
                    
                    if rename:
                        proto = " (" + proto + ").ovpn"
                        new_name = dest_name.replace(".ovpn", proto)   
                        if not xbmcvfs.exists(new_name):
                            xbmcvfs.rename(dest_name, new_name)
                            detail.append("  Renamed to " + new_name + "\n")
                        else:
                            detail.append("  WARNING, couldn't rename file to " + new_name + " as a file with that name already exists\n")
                else:
                    # Copy the ovpn file, don't update it
                    infoTrace("import.py", "Copying " + oname + " to " + dest_name)
                    detail.append("Copying " + oname + " to " + dest_name + "\n")
                    xbmcvfs.copy(oname, dest_name)
                if progress.iscanceled():
                    cancel = True
                    break
    except Exception as e:
        errorTrace("import.py", "Failed to copy (or update) file")
        errorTrace("import.py", str(e))
        success = False
        errorMessage = "Failed to copy (or update) selected files.  Check the log."
        
    progress_message = "Outputting results of import wizard"
    progress.update(100, progress_title, progress_message)
    xbmc.sleep(500)   
    
    # General import results
    summary.append("\n=== Summary of import ===\n\n")
    if cancel:
        summary.append("Import was cancelled\n")
    else:
        summary.append("  Imported " + str(len(ovpn_files)) + " .ovpn files and " + str(len(other_files)) + " other files.\n")
        summary.append("\nYou should understand any WARNINGs below, and validate that the files imported have been updated correctly.\n")
        summary.append("If the connection fails, view the VPN log to determine why and use Google to understand the errors and fix any problems.\n")
        summary.append("You can fix any problems by editing your local files and re-importing, or by editing the contents of the userdata directory.\n\n")
        
        if update:
            # Report on how user names and passwords will be handled
            if auth_count > 0:
                if auth_found > 0:
                    # Not using a password as resolved by file
                    addon.setSetting("user_def_credentials", "false")
                    summary.append("The auth-user-pass tag was found " + str(auth_count) + " times, but was resolved using a supplied file so user name and password don't need to be entered.\n")
                    if not auth_found == auth_count:
                        summary.append("  WARNING : The auth-user-pass tag was found " + str(auth_count) + " times, but only resolved using a supplied file " + str(auth_found) + " times. Some connections may not work.\n")
                else:
                    # Using a password as auth-user-pass tag was found
                    addon.setSetting("user_def_credentials", "true")
                    summary.append("The auth-user-pass tag was found " + str(auth_count) + " times so assuming user name and password authentication is used.\n")
                if auth_count < len(ovpn_files):
                    summary.append("  WARNING : The auth-user-pass tag was only found in " + str(auth_count) + " .ovpn files, out of " + str(len(ovpn_files)) + ". Some connections may not work.\n")
            else:
                # Not using a password as no auth-user-pass tag was found
                addon.setSetting("user_def_credentials", "false")
                summary.append("No auth-user-pass tag was found, so assuming user name and password is not needed.\n")
            
            # Report on how keys and certs will be handled
            if (cert_count > 0 or key_count > 0):
                summary.append("The key tag was found " + str(key_count) + " times, and the cert tag was found " + str(cert_count) + " times.\n")
                if cert_found > 0 or key_found > 0:
                    # Key and cert resolved by file so not asking user for them
                    addon.setSetting("user_def_keys", "None")
                    summary.append("The key and certificate don't need to be requested as the key tags were resolved using a supplied file " + str(key_found) + " times, and the cert tags were resolved using a supplied file " + str(cert_found) + " times.\n")
                    if (not cert_found == cert_count) or (not key_found == key_count):
                        summary.append("  WARNING : The key or cert tags were not resolved by a supplied file for all occurrences. Some connections may not work.\n")
                else:
                    if multiple_certs or multiple_keys:
                        # Key and cert tags found with different file names, but no files supplied.  Assume multiple files, user supplied
                        addon.setSetting("user_def_keys", "Multiple")
                        summary.append("Found key and cert tags with multiple filenames, but no key or certificate files were supplied. These will be requested during connection.\n")
                    else:
                        # Key and cert tags found with same file names, but no files supplied.  Assume single file, user supplied
                        addon.setSetting("user_def_keys", "Single")
                        summary.append("Found key and cert tags all with the same filename, but no key or certificate files were supplied. These will be requested during connection.\n")
                if cert_count < len(ovpn_files) or key_count < len(ovpn_files):
                    summary.append("  WARNING : The key tag was found " + str(key_count) + " times, and the cert tag was found " + str(cert_count) + " times. Expected to find one of each in all " + str(len(ovpn_files)) + " .ovpn files. Some connections may not work.\n") 
            else:
                # Embedded key and certs found, so not asking user for them
                addon.setSetting("user_def_keys", "None")
                if (ekey_count > 0 or ecert_count > 0):
                    if ekey_count == ecert_count and key_count == len(ovpn_files):
                        summary.append("Using embedded user keys and certificates so keys and certs don't need to be entered.\n")
                    else:
                        summary.append("  WARNING : Using embedded user keys and certificates, but found " + str(ekey_count) + " keys and " + str(ecert_count) + " certificates in " + str(len(ovpn_files)) + " .ovpn files. There should be one of each in all .ovpn files otherwise some connections may not work.\n")
                else:
                    summary.append("No user key or cert tags were found so assuming this type of authentication is not used.\n")
            
            # Report how many times each of the non .ovpn files were used
            i = 0
            for oname in other_files:
                summary.append("File " + oname + " was found and used in .ovpn files " + str(other_files_count[i]) + " times.\n")
                if not other_files_count[i] == len(ovpn_files):
                    if other_files_count[i] == 0:
                        summary.append("  WARNING : " + oname + " was not used to update any .ovpn files and could be unused.\n")
                    else:
                        summary.append("  WARNING : The number of updates for " + oname + " was different to the number of .ovpn files, " + str(len(ovpn_files)) + ", which could be a problem.\n")
                i += 1
        else:
            summary.append("None of the files were updated during import.\n")
    
    # Open a log file so all changes can be recorded without fouling up the kodi log       
    log_name = getImportLogPath()
    if xbmcvfs.exists(log_name): xbmcvfs.delete(log_name) 
    log_file = open(log_name, 'w') 
    for line in summary:
        log_file.write(line)
    for line in detail:
        log_file.write(line)
    log_file.close()
    
    progress.close()
    xbmc.sleep(100)
    
if success:
    if xbmcgui.Dialog().yesno(addon_name, "Import wizard finished.  You should view the import log to review any issues, enter your user ID and password (if necessary) and then try and validate a VPN connection.", "", "", "OK", "Import Log"):
        popupImportLog()
else:
    xbmcgui.Dialog().ok(addon_name, errorMessage)

# Return to the settings screen
xbmc.executebuiltin("Addon.OpenSettings(service.vpn.manager)")
    
debugTrace("Exit import.py")