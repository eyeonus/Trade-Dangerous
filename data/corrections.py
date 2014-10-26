# Provides an interface for correcting star/station names that
# have changed in recent versions.

corrections = {
    'LOUIS DE LACAILLE PROSPECT': 'Lacaille Prospect',
    'HOPKINS HANGAR': 'Hopkins Hanger',
}

def correct(oldName):
	try:
		return corrections[oldName.upper()]
	except KeyError:
		return oldName

