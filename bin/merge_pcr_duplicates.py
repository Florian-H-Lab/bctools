#!/usr/bin/env python

tool_description = """
Merge PCR duplicates according to random barcode library.

Barcodes containing uncalled base 'N' are removed.
By default output is written to stdout.

Input:
* bed6 file containing alignments with fastq read-id in name field
* fasta library with fastq read-id as sequence ids

Output:
* bed6 file with random barcode in name field and number of PCR duplicates as score, sorted by fields chrom, start, stop, strand, name

Example usage:
- read PCR duplicates from file duplicates.bed and write merged results to file merged.bed:
merge_pcr_duplicates.py duplicates.bed bclibrary.fa --out merged.bed
"""

# status: development
# * TODO:
#     * check memory requirement; free memory for old DataFrames?
#     * add tests with maformed data and take care to give meaningful errors
#       * additional bed fields
#       * not enough bed fields
#       * malformed fasta

import argparse
import logging
from sys import stdout
from Bio import SeqIO
import pandas as pd

# avoid ugly python IOError when stdout output is piped into another program
# and then truncated (such as piping to head)
from signal import signal, SIGPIPE, SIG_DFL
signal(SIGPIPE, SIG_DFL)


def fasta_tuple_generator(fasta_iterator):
    "Yields id, sequence tuples given an iterator over Biopython SeqIO objects."
    for record in input_seq_iterator:
        yield (record.id, str(record.seq))


# parse command line arguments
parser = argparse.ArgumentParser(description=tool_description)

# positional arguments
parser.add_argument(
    "alignments",
    help="Path to bed6 file containing alignments.")
parser.add_argument(
    "bclib",
    help="Path to fasta barcode library.")
# optional arguments
parser.add_argument(
    "-o", "--outfile",
    help="Write results to this file.")
# misc arguments
parser.add_argument(
    "-v", "--verbose",
    help="Be verbose.",
    action="store_true")
parser.add_argument(
    "-d", "--debug",
    help="Print lots of debugging information",
    action="store_true")

args = parser.parse_args()

if args.debug:
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(filename)s - %(levelname)s - %(message)s")
elif args.verbose:
    logging.basicConfig(level=logging.INFO, format="%(filename)s - %(levelname)s - %(message)s")
else:
    logging.basicConfig(format="%(filename)s - %(levelname)s - %(message)s")
logging.info("Parsed arguments:")
logging.info("  alignments: '{}'".format(args.alignments))
logging.info("  bclib: '{}'".format(args.bclib))
if args.outfile:
    logging.info("  outfile: enabled writing to file")
    logging.info("  outfile: '{}'".format(args.outfile))
logging.info("")

# load barcode library into dictionary
input_handle = open(args.bclib, "rU")
input_seq_iterator = SeqIO.parse(input_handle, "fasta")
bcs = pd.DataFrame.from_records(
    data=fasta_tuple_generator(input_seq_iterator),
    columns=["read_id", "bc"])

# load alignments
alns = pd.read_csv(
    args.alignments,
    sep="\t",
    names=["chrom", "start", "stop", "read_id", "score", "strand"])

# combine barcode library and alignments
bcalib = pd.merge(
    bcs, alns,
    on="read_id",
    how="inner",
    sort=False)
if bcalib.empty:
    raise Exception("ERROR: no common entries for alignments and barcode library found. Please check your input files.")
n_alns = len(alns.index)
n_bcalib = len(bcalib.index)
if n_bcalib < n_alns:
    logging.warning(
        "{} of {} alignments could not be associated with a random barcode.".format(
            n_alns - n_bcalib, n_alns))

# remove entries with barcodes that has uncalled base N
bcalib_cleaned = bcalib.drop(bcalib[bcalib.bc.str.contains("N")].index)
n_bcalib_cleaned = len(bcalib_cleaned)
if n_bcalib_cleaned < n_bcalib:
    msg = "{} of {} alignments had random barcodes containing uncalled bases and were dropped.".format(
        n_bcalib - n_bcalib_cleaned, n_bcalib)
    if n_bcalib_cleaned < (0.8 * n_bcalib):
        logging.warning(msg)
    else:
        logging.info(msg)

# count and merge pcr duplicates
# grouping sorts by keys, so the ouput will be properly sorted
merged = bcalib_cleaned.groupby(['chrom', 'start', 'stop', 'strand', 'bc']).size().reset_index()
merged.rename(columns={0: 'ndupes'}, copy=False, inplace=True)

# write coordinates of crosslinking event alignments
eventalnout = (open(args.outfile, "w") if args.outfile is not None else stdout)
merged.to_csv(
    eventalnout,
    columns=['chrom', 'start', 'stop', 'bc', 'ndupes', 'strand'],
    sep="\t", index=False, header=False)
eventalnout.close()