#!/usr/bin/env python

tool_description = """
Given coordinates of the aligned reads, calculate positions of the crosslinked nucleotides.
Crosslinked nts are assumed to be one nt upstream of the 5'-end of the read.

By default output is written to stdout.

Input:
* bed6 file containing coordinates of aligned reads
* bed6 file containing coordinates of crosslinking events

Example usage:
- convert read coordinates from file in.bed to coordinates of the crosslinking events, written to out.bed:
coords2clnt.py in.bed --outfile out.bed

Status:
- development
"""

import argparse
import logging
from sys import stdout
from pybedtools import BedTool
from pybedtools.featurefuncs import five_prime
# avoid ugly python IOError when stdout output is piped into another program
# and then truncated (such as piping to head)
from signal import signal, SIGPIPE, SIG_DFL
signal(SIGPIPE, SIG_DFL)

# parse command line arguments
parser = argparse.ArgumentParser(description=tool_description)

# positional arguments
parser.add_argument(
    "infile",
    help="Path to bed input file.")
# optional arguments
parser.add_argument(
    "-o", "--outfile",
    help="Write results to this file.")
parser.add_argument(
    "-v", "--verbose",
    help="Be verbose.",
    action="store_true")
parser.add_argument(
    "-d", "--debug",
    help="Print lots of debugging information",
    action="store_true")

# handle arguments
args = parser.parse_args()
if args.debug:
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(filename)s - %(levelname)s - %(message)s")
elif args.verbose:
    logging.basicConfig(level=logging.INFO, format="%(filename)s - %(levelname)s - %(message)s")
else:
    logging.basicConfig(format="%(filename)s - %(levelname)s - %(message)s")
logging.info("Parsed arguments:")
if args.outfile:
    logging.info("  outfile: enabled writing to file")
    logging.info("  outfile: '{}'".format(args.outfile))
logging.info("  outfile: '{}'".format(args.outfile))
logging.info("")

# data processing
alns = BedTool(args.infile)
clnts = alns.each(five_prime, upstream=1, downstream=0)

# write to file or to stdout
if args.outfile:
    clnts.saveas(args.outfile)
else:
    tmptool = clnts.saveas()
    logging.debug("results written to temporary file :" + tmptool.fn)
    tmp = open(tmptool.fn)
    for line in tmp:
        stdout.write(line)
    tmp.close()
