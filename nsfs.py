#!/usr/bin/python

from time import time
from StringIO import StringIO

import stat    # for file properties
import os      # for filesystem modes (O_RDONLY, etc)
import errno   # for error number codes (ENOENT, etc)
               # - note: these must be returned as negatives


# pull in some spaghetti to make this stuff work without fuse-py being installed
try:
    import _find_fuse_parts
except ImportError:
    pass
import fuse
from fuse import Fuse

if not hasattr(fuse, '__version__'):
    raise RuntimeError, \
        "your fuse-py doesn't know of fuse.__version__, probably it's too old."

fuse.fuse_python_api = (0, 2)

class DefaultStat(fuse.Stat):
    def __init__(self):
        self.st_mode = 0
        self.st_ino = 0
        self.st_dev = 0
        self.st_nlink = 0
        self.st_uid = 0
        self.st_gid = 0
        self.st_size = 0
        self.st_atime = 0
        self.st_mtime = 0
        self.st_ctime = 0

class DefaultStatVfs(fuse.StatVfs):
    def __init__(self):
        self.f_bavail = 0
        self.f_bfree = 0
        self.f_blocks = 0
        self.f_bsize = 0
        self.f_favail = 0
        self.f_ffree = 0
        self.f_files = 0
        self.f_flag = 0
        self.f_frsize = 0
        self.f_namemax = 0
        self.n_fields = 0
        self.n_sequence_fields = 0
        self.n_unamed_fields = 0

class NamespaceFS(Fuse):
    """Generates a file system from a python namespace, for kicks.
    """

    def __init__(self, *args, **kw):
        Fuse.__init__(self, *args, **kw)

        self.context = self.GetContext()
        #self.file_class = NsfsFile
        print '*** init complete'

    def getattr(self, path):
        """
        - st_mode (protection bits)
        - st_ino (inode number)
        - st_dev (device)
        - st_nlink (number of hard links)
        - st_uid (user ID of owner)
        - st_gid (group ID of owner)
        - st_size (size of file, in bytes)
        - st_atime (time of most recent access)
        - st_mtime (time of most recent content modification)
        - st_ctime (platform dependent; time of most recent metadata change on 
                    Unix, or the time of creation on Windows).
        """
        print '*** getattr', path

        st = DefaultStat()
        #st.st_uid = self.context['uid']
        #st.st_gid = self.context['gid']
       
        if path == '/':
            # root directory
            st.st_mode = stat.S_IFDIR | 0755
            st.st_nlink = 2 
            return st 

        # we want this in the form 'module/submod/stuff'
        l = path.strip('/').split('/')
        
        # recursively check the namespace
        try:
            l[0] = globals()[l[0]] 
            if len(l) > 1:
                thing = reduce(getattr, l)
            else:
                thing = l[0]
        except:
            return -errno.ENOENT # nope, not there
       
        # for now, only modules are directories 
        if isinstance(thing, type(fuse)):
            st.st_mode = stat.S_IFDIR | 0755
            st.st_nlink = 2 
        else:
            st.st_mode = stat.S_IFREG | 0444
            st.st_size = len(str(thing))  # how big?
            st.st_nlink = 1
        return st 

    def readdir(self, path, offset):
        print '*** readdir', path, offset
        if path == '/':
            retl = globals().keys()
        else:
            # we want this in the form 'module/submod/stuff'
            l = path.strip('/').split('/')

            # recursively check the namespace
            try:
                print '* trying ', l
                l[0] = globals()[l[0]]
                if len(l) == 1:
                    retl = l[0].__dict__.keys()
                else:
                    retl = reduce(getattr, l).__dict__.keys()
            except:
                raise IOError(-errno.ENOENT) # nope, not there

        retl.insert(0, '..')
        retl.insert(0, '.')
        for r in retl:
            yield fuse.Direntry(r)

    def open ( self, path, flags ):
        print '*** open', path, flags

        # we want this in the form 'module/submod/stuff'
        l = path.strip('/').split('/')

        # recursively check the namespace
        try:
            print '* trying ', l
            l[0] = globals()[l[0]]
            if len(l) == 1:
                thing = l[0]
            else:
                thing = reduce(getattr, l)
        except:
            raise IOError(-errno.ENOENT) # nope, not there

        # only allow read unless it's a string
        writeok = False
        if isinstance(thing, type(".")):
            writeok = True
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) and writeok:
            return
        elif (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES

    def read ( self, path, length, offset ):
        print '*** read', path, length, offset
        # we want this in the form 'module/submod/stuff'
        l = path.strip('/').split('/')

        # recursively check the namespace
        try:
            print '* trying ', l
            l[0] = globals()[l[0]]
            if len(l) == 1:
                thing = l[0]
            else:
                thing = reduce(getattr, l)
        except:
            raise IOError(-errno.ENOENT) # nope, not there

        tstr = str(thing)
        slen = len(tstr)
        if offset < tstr:
            if offset + length > slen:
                size = slen - offset
            buf = tstr[offset:offset+length]
        else:
            buf = ''
        return buf

    def statfs ( self ):
        print '*** statfs'
        #return -errno.ENOSYS
        fst = DefaultStatVfs()
        fst.f_namemax = 256
        return fst

    def link ( self, targetPath, linkPath ):
        print '*** link', targetPath, linkPath
        t = targetPath.strip('/').split('/')

        # recursively check the namespace; target can't be / for now
        try:
            print '* trying ', t
            t[0] = globals()[t[0]]
            if len(t) == 1:
                target = t[0]
            else:
                target = reduce(getattr, t)
        except:
            return -errno.ENOENT # nope, not there

        l = linkPath.strip('/').split('/')
        if (len(l) == 1) and (l[0] != '') and not (l[0] in globals().keys()):
            # easy, good to go
            globals()[l[0]] = target
            print '* trying easy ', l[0], target
            return

        # otherwise...
        # recursively check the namespace; link can't be /
        try:
            print '* trying ', l
            l[0] = globals()[l[0]]
            if len(l) == 1:
                raise IOError(-errno.ENOENT) # can't do root or existing
            elif len(l) == 2:
                lp = l[0]
            else:
                lp = reduce(getattr, l[:-1]) # want the parent of the link
        except:
            return -errno.ENOENT # nope, not there
       
        # if that all worked out with no errors...
        lp.__setattr__(l[-1], target)

    def unlink ( self, path ):
        print '*** unlink', path

        l = path.strip('/').split('/')
        if (len(l) == 1) and (l[0] != '') and (l[0] in globals().keys()):
            # easy, good to go
            del globals()[l[0]]
            return

        try:
            print '* trying ', l
            l[0] = globals()[l[0]]
            if len(l) == 1:
                return -errno.ENOENT # something is wrong, shouldn't get here
            elif len(l) == 2:
                lp = l[0]
            else:
                lp = reduce(getattr, l[:-1]) # want the parent of the link
        except:
            return -errno.ENOENT # nope, not there
        lp.__delattr__(l[-1])

    def write ( self, path, buf, offset ):
        print '*** write', path, buf, offset
        # we want this in the form 'module/submod/stuff'
        l = path.strip('/').split('/')

        # recursively check the namespace
        try:
            print '* trying ', l
            l[0] = globals()[l[0]]
            if len(l) == 1:
                thing = l[0]
            else:
                thing = reduce(getattr, l)
        except:
            print '* ACTUALLY CAN\'T FIND'
            raise IOError(-errno.ENOENT) # nope, not there
        
        if not isinstance(thing, type(".")):
            print '* WRONG TYPE'
            raise IOError(-errno.ENOENT) # wrong file type
 
        # Kind of a slow way to go?
        sfile = StringIO(thing)
        sfile.seek(offset)
        sfile.write(buf)
        sfile.flush()
        thing = sfile.getvalue()
        sfile.close()

        # recursively check the namespace
        l = path.strip('/').split('/')
        #try:
        if len(l) == 1:
            globals()[l[0]] = thing
            return len(buf)
        l[0] = globals()[l[0]]
        tp = reduce(getattr, l[:-1])
        tp.__setattr__(l[-1], thing)
        print '* TRIED ', thing
        return len(buf)
        #except: #    raise IOError(-errno.ENOENT) # nope, not there

    def release ( self, path, flags ):
        print '*** release', path, flags
        return -errno.ENOSYS

    def fsync ( self, path, isFsyncFile ):
        print '*** fsync', path, isFsyncFile
        return -errno.ENOSYS

    def mknod ( self, path, mode, dev ):
        print '*** mknod', path, oct(mode), dev
        return -errno.ENOSYS

    def rmdir ( self, path ):
        print '*** rmdir', path
        return -errno.ENOSYS

    def getdir(self, path):
        print '*** getdir', path
        return self.readdir(path, 0)

    def mythread ( self ):
        print '*** mythread'
        return -errno.ENOSYS

    def chmod ( self, path, mode ):
        print '*** chmod', path, oct(mode)
        return -errno.ENOSYS

    def chown ( self, path, uid, gid ):
        print '*** chown', path, uid, gid
        return -errno.ENOSYS

    def mkdir ( self, path, mode ):
        print '*** mkdir', path, oct(mode)
        return -errno.ENOSYS

    def readlink ( self, path ):
        print '*** readlink', path
        return -errno.ENOSYS

    def rename ( self, oldPath, newPath ):
        print '*** rename', oldPath, newPath
        globals()[path1] = globals()[path]
        del globals()[path]
        #return -errno.ENOSYS

    def symlink ( self, targetPath, linkPath ):
        print '*** symlink', targetPath, linkPath
        return -errno.ENOSYS

    def truncate ( self, path, size ):
        print '*** truncate', path, size
        return -errno.ENOSYS

    def utime ( self, path, times ):
        print '*** utime', path, times
        return -errno.ENOSYS

# This isn't actually used yet
class NsfsFile(object):

    def init(self, path, flags, mode=None):

        # if mode != None: NEW FILE

        # we want this in the form 'module/submod/stuff'
        l = path.strip('/').split('/')

        # recursively check the namespace
        try:
            l[0] = globals()[l[0]]
            self.thing = reduce(getattr, l)
        except:
            return -errno.ENOENT # nope, not there
        self.tstr = str(self.thing)
        self.tfile = StringIO(self.tfile)

    def read(self, len, offset):
        #return -errno.ENOSYS
        return read(self.tfile, len, offset)

    def release(self, flags):
        self.tfile.close()

def main():
    usage="""
Experimental Python Namespace Filesystem

""" + Fuse.fusage
    server = NamespaceFS(version="%prog " + fuse.__version__,
        usage=usage,
        dash_s_do='setsingle')
    server.parse(errex=1)
    server.flags = 0
    server.multithreaded = 0
    print "let's go!"
    server.main()

if __name__ == '__main__':
    main()
