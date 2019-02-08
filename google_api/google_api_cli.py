'''
The cli module interacts with the user via the comman line module through
the argparse
'''
import argparse
import google_api_core as gac

parser = argparse.ArgumentParser()
parser.add_argument("service", help="specify the google service to connec to, [drive, gmail]")

# TODO figure out best options/arguments
# having a positional arg for which google service is being called might be
# beneficial, python google_api drive or python google_api gmail
