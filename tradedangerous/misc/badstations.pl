#! /usr/bin/perl

# Load the headings from Station.csv
$heading = `head -1 data/Station.csv`;
$results = 0;

open(BADSTATIONS, ">tmp/badstations.csv") || die "Can't open tmp/badstations.csv file";
sub print_bad_station($$) {
    my ($sys, $stn) = (@_);
    print(BADSTATIONS $heading) if (!$results);
    $sys =~ s/'/''/g;
    $stn =~ s/'/''/g;
    print(BADSTATIONS "'$sys','$stn',-1,'?','?'\n");
}

open(CORRECTIONS, ">tmp/corrections.py") || die "Can't open tmp/corrections.py";
sub print_correction($$) {
    my ($sys, $stn) = (@_);
    $sys =~ s/"/\\"/g;
    $stn =~ s/"/\\"/g;
    print(CORRECTIONS qq!\t"\U${sys}\E/\U${stn}\U":\t\tDELETED,\n!);
}

while (<>) {
    next unless m!Ignoring '(.*)/(.*)' because it looks like OCR derp!;
    my ($sys, $stn) = ($1, $2);
    print_bad_station($sys, $stn);
    print_correction($sys, $stn);
    ++$results;
}
