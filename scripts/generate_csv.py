"""
This script generates a CSV file for the questions in each lot.

The order of fields in the generated file is the same as we had for G-Cloud-6:
"Page title", "Question", "Hint", "Answer 1", "Answer 2", ...

Before running this you will need to:
pip install -r requirements_for_script.txt

Usage:
    scripts/generate-csv.py <target_directory>
"""
import unicodecsv
import os
from dmutils.content_loader import ContentLoader

from docopt import docopt


new_service_content = ContentLoader(
    'app/new_service_manifest.yml', 'app/content/g6/'
)
lots = ['PaaS', 'SaaS', 'IaaS', 'SCS']


def generate_csvs(target_directory):

    if not os.path.exists(target_directory):
        os.makedirs(target_directory)

    for lot in lots:
        content = new_service_content.get_builder().filter(
            {'lot': lot}
        )
        with open('{}/g7-{}-questions.csv'.format(target_directory, lot), 'wb') as csvfile:
            writer = unicodecsv.writer(csvfile, delimiter=',', quotechar='"')
            header = ["Page title", "Question", "Hint"]
            header.extend(
                ["Answer {}".format(i) for i in range(1, max_options(content)+1)]
            )
            writer.writerow(header)
            for section in content.sections:
                for question in section.questions:
                    row = [
                        section.name,
                        question.get('question'),
                        question.get('hint')
                    ]
                    options = [option['label'] for option in question.get('options', []) if 'label' in option]
                    row.extend(options)

                    writer.writerow(row)


def max_options(content):
    maxlen = 0
    for section in content.sections:
        for question in section.questions:
            optlen = len(question.get('options', []))
            if optlen > maxlen:
                maxlen = optlen
    return maxlen


if __name__ == '__main__':
    arguments = docopt(__doc__)

    generate_csvs(target_directory=arguments['<target_directory>'])
