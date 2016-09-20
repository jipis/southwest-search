import argparse
import cookielib
import itertools
import json
import mechanize
import re
import tabulate
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

cities = ['GSP', 'FNT', 'BOS', 'OAK', 'LIT', 'BOI', 'SAN', 'DCA', 'LBB', 'BWI',
          'PIT', 'RIC', 'SAT', 'JAX', 'IAD', 'JAN', 'HRL', 'CHS', 'EYW', 'BNA',
          'PHL', 'SNA', 'SFO', 'PHX', 'LAX', 'MAF', 'LAS', 'CRP', 'CMH', 'FLL',
          'DEN', 'DTW', 'BUR', 'ROC', 'GEG', 'BUF', 'GRR', 'BDL', 'DSM', 'EWR',
          'MHT', 'PBI', 'RNO', 'OKC', 'IND', 'ATL', 'ISP', 'SMF', 'BKG', 'PVD',
          'SEA', 'ECP', 'ICT', 'MDW', 'RDU', 'PDX', 'CLE', 'SJU', 'AUS', 'CLT',
          'SJC', 'ELP', 'OMA', 'MEM', 'TUS', 'ALB', 'TUL', 'ORF', 'MKE', 'MSY',
          'MSP', 'CAK', 'TPA', 'DAL', 'DAY', 'ONT', 'STL', 'ABQ', 'HOU', 'SLC',
          'MCO', 'RSW', 'BHM', 'MCI', 'PNS', 'LGA', 'AMA', 'SDF', 'PWM']


def page_grab(date, depart, arrive):
    br = mechanize.Browser()

    # Cookie Jar
    cj = cookielib.LWPCookieJar()
    br.set_cookiejar(cj)

    # Browser options
    br.set_handle_equiv(True)
    br.set_handle_redirect(True)
    br.set_handle_referer(True)
    br.set_handle_robots(False)

    # Follows refresh 0 but not hangs on refresh > 0
    br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=1)

    # Want debugging messages?
    # br.set_debug_http(True)
    # br.set_debug_redirects(True)
    # br.set_debug_responses(True)

    br.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]

    br.open("http://www.southwest.com/flight/search-flight.html")
    br.select_form(name="buildItineraryForm")
    br["twoWayTrip"] = ["false"]
    br["originAirport"] = [depart]
    br["destinationAirport"] = [arrive]
    br["outboundDateString"] = date

    return br.submit(name="submitButton").read()


def page_parse(data):

    page = BeautifulSoup(data, 'html.parser')

    elements = []
    for x in page.find_all('input'):
        try:
            if "upsellOutboundRadio" in x.attrs['class']:
                elements.append(x)
        except:
            continue

    titleRE = re.compile("Departing flight ([0-9/]*) \$([0-9]*) ([0-9]?[0-9]:[0-9]{2}(?:AM|PM)) depart " +
                         "([0-9]?[0-9]:[0-9]{2}(?:AM|PM)) arrive (.*)")
    valueRE = re.compile("([0-9]{4} [0-9]{2} [0-9]{2}),([^,])*,.*")

    options = {}
    for element in elements:
        try:
            titlematch = titleRE.match(element.attrs['title'])
            valuematch = valueRE.match(element.attrs['value'])

            depart = datetime.strptime(valuematch.group(1) + " " + titlematch.group(3), "%Y %m %d %I:%M%p")
            arrive = datetime.strptime(valuematch.group(1) + " " + titlematch.group(4), "%Y %m %d %I:%M%p")
            if arrive < depart:
                arrive += timedelta(days=1)

            if "Nonstop" in titlematch.group(5):
                num_stops = 0
            else:
                num_stops = int(titlematch.group(5)[0])

            if titlematch.group(1) in options:
                options[titlematch.group(1)]["fares_usd"].append(int(titlematch.group(2)))
                options[titlematch.group(1)]["fares_usd"].sort()
            else:
                options[titlematch.group(1)] = ({"fares_usd": [int(titlematch.group(2))],
                                                 "depart": depart.isoformat(),
                                                 "arrive": arrive.isoformat(),
                                                 "stop_info": titlematch.group(5),
                                                 "depart_tz": valuematch.group(2),
                                                 "flight_num": titlematch.group(1),
                                                 "num_stops": num_stops})
        except Exception as e:
            print e

    return options.values()


def pretty_print_flights(flights, sort, lowest_fare, max_stops):
    keys = ["flight_num", "depart", "arrive", "fares_usd", "stop_info", "num_stops"]
    flight_list = []
    for flight in flights:
        if max_stops is not None and flight["num_stops"] > max_stops:
            continue

        if lowest_fare:
            flight["fares_usd"] = min(flight["fares_usd"])

        thisflight = []
        for key in keys:
            thisflight.append(flight[key])

        flight_list.append(thisflight)

    flight_list.sort(key=lambda l: l[keys.index(sort)])
    print tabulate.tabulate(flight_list, headers=keys)

parser = argparse.ArgumentParser()
parser.add_argument('-a', '--arrival-cities', action='store', nargs="+", choices=cities)
parser.add_argument('-d', '--departure-cities', action='store', nargs="+", choices=cities)
parser.add_argument('-t', '--dates', action='store', nargs="+")
parser.add_argument('-s', '--sort', action='store', choices=["flight_num", "depart", "arrive", "fares_usd",
                                                             "stop_info", "num_stops"])
parser.add_argument('-l', '--show-only-lowest-fare', action='store_true', help="Only shows the lowest fare " +
                    "for each route.")
parser.add_argument('-m', '--max-stops', type=int, help="Filter for flights with this many stops or less.")
parser.add_argument('-e', '--export-file', type=str, help="Save results to a file. Useful if you want to " +
                    "sort and filter the same results different ways without re-making the server requests.")
parser.add_argument('-i', '--import-file', type=str, help="Load results from a file create with --export.")

args = parser.parse_args(namespace=None)

if args.import_file is not None:
    with open(args.import_file, "r") as f:
        options = json.load(f)
else:
    options = []
    i = 0
    possible = len(args.dates) * len(args.departure_cities) * len(args.arrival_cities)

    for route in itertools.product(args.dates, args.departure_cities, args.arrival_cities):
        try:
            page = page_grab(*route)
            options += page_parse(page)
            i += 1
            print "Processed %i/%i" % (i, possible)
            if i < possible:
                # do not decrease this - avoids putting undue strain on SW's servers
                time.sleep(2)
        except Exception as e:
            print e
            continue

if args.export_file is not None:
    with open(args.export_file, "w") as f:
        json.dump(options, f)

pretty_print_flights(options, args.sort, args.show_only_lowest_fare, args.max_stops)
