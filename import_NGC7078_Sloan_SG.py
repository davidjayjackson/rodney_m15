import sqlite3 as sqlite
import datetime
from os import path
import filecmp

"""
Project global variables here:
Paths, folders, and names.
"""
project_path = '/Users/howe/dwsktop/m15/'
to_import_folder = path.join(project_path, 'to_import')
print to_import_folder
imported_folder = path.join(project_path, 'imported')
database_name = 'NGC7078.sqlite'
database = sqlite.connect(path.join(project_path, database_name))
cursor = database.cursor()
table_name = "Sloan_SG"


class DataLine(object):
    __slots__ = ['STARNAME', 'DATE', 'MAG','MERR','FILT','TRANS','MTYPE','CNAME','CMAG','KNAME','KMAG','AMASS','GROUP','CHART','NOTES']
    """
    Represents the data contained in a dataline.
    Includes the date, time, and star mag data.
    
    Parse the filename to get the date, parse the line to get the time and star data.
    Create a DataLine object to contain the data pieces.         "self.DATE = DATE.replace('/', '-')
    """
        self.STARNAME = STARNAME.strip()
        self.DATE = DATE.strip()
        self.MAG = MAG.strip()
        self.MERR = MERR.strip()
        self.FILT = FILT.strip()
        self.TRANS = TRANS.strip()
        self.MTYPE = MTYPE.strip()
        self.CNAME = CNAME.strip()
        self.CMAG = CMAG.strip()
        self.KNAME = KNAME.strip()
        self.KMAG = KMAG.strip()
        self.AMASS = AMASS.strip()
        self.GROUP = GROUP.strip()
        self.CHART = CHART.strip()
        self.NOTES = NOTES.strip() 
        
    def __init__(self, line, filename):
        super(DataLine, self).__init__()
        STARNAME,DATE,MAG,MERR,FILT,TRANS,MTYPE,CNAME,CMAG,KNAME,KMAG,AMASS,GROUP,CHART,NOTES = line.split(',')
        self.STARNAME = STARNAME
        self.DATE = DATE
        self.MAG = MAG
        self.MERR = MERR
        self.FILT = FILT
        self.TRANS = TRANS
        self.MTYPE = MTYPE
        self.CNAME = CNAME
        self.CMAG = CMAG
        self.KNAME = KNAME
        self.KMAG = KMAG
        self.AMASS = AMASS
        self.GROUP = GROUP
        self.CHART = CHART
        self.NOTES = NOTES 
     
    def insert_into_db(self, database):
        sql = "insert into %s values ('%s',%s,%s,%s,'%s','%s','%s','%s',%s,'%s',%s,%s,%s,'%s','%s');" % (table_name, self.STARNAME, self.DATE, self.MAG, self.MERR, self.FILT, self.TRANS, self.MTYPE, self.CNAME, self.CMAG, self.KNAME, self.KMAG, self.AMASS, self.GROUP, self.CHART, self.NOTES)
        database.execute(sql)


def setup_db():
    try:
        sql = "create table %s (STARNAME text, DATE real, MAG real, MERR real, FILT text, TRANS text, MTYPE text, CNAME text, CMAG real, KNAME text, KMAG real, AMASS real, GROUP real, CHART text, NOTES text)" % (table_name)
        database.execute(sql)
        database.commit()
        print "... table created..."
    except:
        print "... table already exists..."


def import_file(filename):
    s = 0; f = 0
    print "... importing %s..." %(filename)
    print path.join(to_import_folder, filename)
    with open(path.join(to_import_folder, filename)) as data_file:
        for line in data_file:
            try:
                data_point = DataLine(line.rstrip('\n\r'), filename)
                data_point.insert_into_db(database)
                s += 1
            except:
                f += 1
                print "... %s " %(line)
    
    s += 1
    database.commit()
    return (s, f)


"""
Get unique (new) files from the to_import_folder so don't insert any new files
Try setting up the database in case not previously created.
Import each file by iterating over lines, creating a DataLine object for each line,
and calling the object to insert itself into the database.
"""
files = filecmp.dircmp(to_import_folder, imported_folder).left_only
print files
setup_db()

success = 0
failures = 0

start_time = datetime.datetime.now()
for f in files:
    (suc, fail) = import_file(f)
    success += suc
    failures += fail

end_time = datetime.datetime.now()
time_to_import = end_time - start_time
print "Time to import = %d seconds" % (time_to_import.seconds)
print "Success = %d, Failures = %d, ratio = %.7f" %(success, failures, float(failures)/ (success + failures))


