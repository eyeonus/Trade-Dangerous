/*
 * Coordinate ID generator:
 * Takes a set of 3d coordinates (x, y, z), truncates to 2dp and then
 * generates a base64-like(*) representation that can be used as an id
 * for the object.
 *
 * The actual encoding is not base64, since base64 contains characters
 * that present a problem when used, e.g, in URIs. I replaced the '+'
 * and '/' characters with '_' and '.' respectively.
 *
 * Example usage:
 *   coord_to_id64(51.5625, 32.1875, -27.125)
 * Generates:
 *   "1gA:Oi:-Go"
 *
 * A reversing function is also provided.
 *
 * Original Author: Oliver "kfsone" Smith <oliver@kfs.org>
 * Released under the "use it with attribution" license.
 */

var alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_.";
var precision = 100.;

function coord_to_d64(coord) {
    var i = parseInt(Math.abs(coord * precision));

    var digits = ""
	do {
        digits = alphabet[i & 63] + digits;
		i >>= 6;	// shift right by a digit (>>= 6)
	} while (i > 0);

	return (coord < 0) ? ("-"+digits) : (digits);
}

function d64_to_coord(d64) {
	var divisor = precision;
	var pos = 0;
	if (d64[0] == '-') {
		divisor = -divisor;
		pos++;
	}

	var number = 0;
	for ( ; pos < d64.length ; ++pos ) {
        var value = alphabet.indexOf(d64[pos]);
		if (value < 0)
			throw "Invalid d64 value: " + d64;
        number = (number * 64) + value;
	}

    return number / divisor;
}

function pos_to_id64(x, y, z) {
    return coord_to_d64(x) + ':' + coord_to_d64(y) + ':' + coord_to_d64(z);
}

function id64_to_pos(id64) {
	d64s = id64.split(':');
	return [ d64_to_coord(d64s[0]),
			 d64_to_coord(d64s[1]),
			 d64_to_coord(d64s[2])
			];
}

/*
 * Test cases
 *

function test_conv(testPos) {
    id64 = pos_to_id64(testPos[0], testPos[1], testPos[2]);
	document.write("id64 [", testPos.join(','), "] = ", id64, "\n")
	pos = id64_to_pos(id64);
	document.write("pos of ", id64, " = [", pos.join(','), "]\n");
}

var test1 = [ 51.5625,32.1875,-27.125 ];
var test2 = [ -154.65625,40.34375,-82.78125 ];

test_conv(test1);
test_conv(test1);
test_conv(test2);

*/

