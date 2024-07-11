
from FaceDatabaseManager import FaceDatabaseManager

fdm = FaceDatabaseManager('database')
for member in fdm.get_name_list():
    fdm.rename_face(member, 'Johnny Lue')