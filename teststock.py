import sys
import requests
import yaml

class PromError(Exception):
    def __init__(self, expression, message):
        self.expression = expression
        self.message = message

class PromDateFormatError(PromError):
    pass

class PromStatusError(PromError):
    pass

def transform_labels_query(labels: dict) -> str:
    return "{" + ",".join("{}=\"{}\"".format(*i) for i in labels.items()) + "}"

def timeconverter(string: str) -> int:
    char = string[len(string) - 1]
    try:
        if char == "s":
            return int(string[:-1])
        elif char == "m":
            return int(string[:-1]) * 60
        elif char == "h":
            return int(string[:-1]) * 3600
        elif char == "d":
            return int(string[:-1]) * 86400
        elif char == "w":
            return int(string[:-1]) * 604800
        elif char == "y":
            return int(string[:-1]) * 31449600
        else:
            raise PromDateFormatError(string,
                                      'Date is invalid : {0}. Last character {1} not in ["s","m","h","w","y"]'.format(
                                          string, string[len(string) - 1]))
    except ValueError:
        raise PromDateFormatError(string,
                                  'Date is invalid : {0}. Unable to convert {1} to integer'.format(string, string[:-1]))

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print('Usage: {0} http://localhost:9090 30d'.format(sys.argv[0]))
        sys.exit(1)

    base_url = sys.argv[1] + '/api/v1'
    config_url = base_url + '/status/config'
    target_url = base_url + '/targets'
    query_url = base_url + '/query'
    nb_samples_per_seconds = 0

    try:
        retention_time = timeconverter(sys.argv[2])
        config_request = requests.get(config_url)
        if config_request.json()['status'] != "success":
            raise PromStatusError(config_url, 'Prometheus config\'s status is not in a good state')
        config = yaml.safe_load(config_request.json()['data']['yaml'])
    except PromError as e:
        print(e.message)
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print('Unable to connect to Prometheus with url ' + config_url)
        sys.exit(1)

    target_request = requests.get(target_url)
    targets = target_request.json()['data']['activeTargets']

    for target in targets:
        scrape_interval = timeconverter(
            target['scrapeInterval'] if 'scrapeInterval' in target else config['global']['scrape_interval'])
        query = requests.get(query_url, params={'query': transform_labels_query(target['labels'])})
        nb_samples = len(query.json()['data']['result'])
        print('Target : {0}\nScrape Interval : {1}\nNb. Samples : {2}\n'.format(target['scrapePool'],
                                                                                str(scrape_interval), str(nb_samples)))
        nb_samples_per_seconds += nb_samples / scrape_interval

    print("\n------\nRétention (s): {time_retention}\nNb échantillon par seconde: {nb_samples_per_s}\nTaille Éstimer "
          "(bytes): {size:e}".format(time_retention=retention_time, nb_samples_per_s=int(nb_samples_per_seconds),
                                     size=retention_time * int(nb_samples_per_seconds) * 2))
