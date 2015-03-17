#!/usr/bin/python
# -*- coding: utf8 -*-

# Password list - Manage encrypted textfiles with gpg
# https://github.com/rolfa/gpgedit
# originally from: http://stackoverflow.com/questions/1510105/gnupg-how-to-edit-the-file-without-decrypt-and-save-to-local-disk-first

# Updates:
# Version 1.0.0: tested on Jolla with SailfishOS. Should run on other Linux systems but some paths (GPG, EDITOR, VIEWER) may need to be adjusted.
# Version 1.0.1: code tidied

import os, sys, subprocess, getpass, stat, shutil
from optparse import OptionParser

PRGNAME = os.path.basename(sys.argv[0]).replace('.py', '')
VERSION = '1.0.1'
GPG = '/usr/bin/gpg2'
EDITOR = '/usr/bin/nano'
VIEWER = '/usr/bin/less'

# http://docs.python.org/library/optparse.html#module-optparse
usage='usage: %s [options] filename' % (os.path.basename(sys.argv[0]))
parser = OptionParser(version='%prog ' + VERSION, usage=usage)
parser.add_option('-v', '--verbose', action='store_true', help='Verbose')
parser.add_option('-e', '--edit', action='store_true', help='open decrypted file in editor')
parser.add_option('-c', '--create', action='store_true', help='create empty encrypted file')
(options, args) = parser.parse_args()

VERBOSE = True if options.verbose else False

if options.edit and options.create:
    print 'Error: --edit and --create are exclusive'
    sys.exit(1)

if len(args) != 1:
    print 'Error: wrong number of arguments'
    print usage
    sys.exit(1)

FNAME = args[0]

if not FNAME:
    print 'Error: no filename given'
    sys.exit(1)

if options.create: # create empty encrypted file

    if os.path.exists(FNAME):
        print 'Error: file %s already exists' % FNAME
        sys.exit(1)

    if os.path.exists(FNAME + '.gpg'):
        print 'Error: file %s already exists' % (FNAME + '.gpg')
        sys.exit(1)

    if VERBOSE: print 'creating file'
    open(FNAME, 'a').close() # touch
    passwd = getpass.getpass()
    cmd = '%s --batch --yes --symmetric --passphrase-fd 0 %s' % (GPG, FNAME) # creates file with extension .gpg
    proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE)
    proc.stdin.write(passwd)
    proc.stdin.close()
    if proc.wait() != 0:
        print 'Error encrypting file.'
    os.remove(FNAME)
    sys.exit(0)

else: # use existing file
    if not os.path.exists(FNAME):
        print 'Error: file not found'
        sys.exit(1)

if options.edit:
    READONLY = False
    print 'edit mode'
else:
    READONLY = True
    print 'read only mode'

# make a backup of the encrypted file
bakFile = '%s-%s_backup' % (FNAME, PRGNAME)
shutil.copy(FNAME, bakFile)
dstat = os.stat(FNAME)

#  create temporary directory in tmpfs to work from
tmpDir = '/dev/shm/gpgedit'
n = 0
while True:
    try:
        os.mkdir(tmpDir + str(n))
        break
    except OSError as err:
        if err.errno != 17:  # 17 = file already exists
            raise
    n += 1
tmpDir += str(n)

os.chmod(tmpDir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

try:
    passwd = getpass.getpass()

    # decrypt file
    tmpFile = os.path.join(tmpDir, 'data')
    cmd = '%s --batch -d --passphrase-fd 0 --output %s %s' % (GPG, tmpFile, FNAME)
    proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE)
    proc.stdin.write(passwd)
    proc.stdin.close()
    if proc.wait() != 0:
        raise Exception('Error decrypting file.')

    # record stats of tmp file
    stat = os.stat(tmpFile)

    if READONLY:
        # LESSSECURE is an environment variable to activate secure mode if set to 1. For example it disables invoking an editor to edit the current file being viewed.
        os.system('LESSSECURE=1 %s %s' % (VIEWER, tmpFile)) # invoke viewer
    else:
        os.system('%s %s' % (EDITOR, tmpFile)) # invoke editor
        # see whether data has changed
        stat2 = os.stat(tmpFile)
        if stat.st_mtime == stat2.st_mtime and stat.st_size == stat2.st_size:
            print 'Data unchanged; not writing encrypted file.'
        else:
            # re-encrypt, write back to original file
            cmd = '%s --batch --yes --symmetric --passphrase-fd 0 --output %s %s' % (GPG, FNAME, tmpFile)
            proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE)
            proc.stdin.write(passwd)
            proc.stdin.close()
            if proc.wait() != 0:
                raise Exception('Error encrypting file.')

except Exception, e:
    # If there was an error AND the data file was modified, restore the backup.
    dstat2 = os.stat(FNAME)
    if dstat.st_mtime != dstat2.st_mtime or dstat.st_size != dstat2.st_size:
        print 'Error occurred, restored encrypted file from backup.'
        shutil.copy(bakFile, FNAME)
    print 'Fatal: %s' % e

shutil.rmtree(tmpDir)
os.remove(bakFile)
