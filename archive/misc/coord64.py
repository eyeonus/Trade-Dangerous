# Coordinate ID generator:
# Takes a set of 3d coordinates (x, y, z), truncates to 2dp and then
# generates a base64-like(*) representation that can be used as an id
# for the object.
#
# The actual encoding is not base64, since base64 contains characters
# that present a problem when used, e.g, in URIs. I replaced the '+'
# and '/' characters with '_' and '.' respectively.
#
# Example usage:
#   coord_to_id64(51.5625, 32.1875, -27.125)
# Generates:
#   "1gA:Oi:-Go"
#
# A reversing function is also provided.
#
# Original Author: Oliver "kfsone" Smith <oliver@kfs.org>
# Released under the "use it with attribution" license.

import string


alphabet = string.digits + string.ascii_lowercase + string.ascii_uppercase + '_.'
precision = 100.


def coord_to_d64(coord):
    i = int(abs(coord * precision))
    
    digits = ""
    while True:
        digits = alphabet[i & 63] + digits
        i >>= 6   # divides by 64, or one digit
        if i == 0:
            break
    
    sign = '-' if coord < 0 else ''
    return sign + digits


def d64_to_coord(d64):
    divisor, digits = precision, d64
    if d64.startswith('-'):
        divisor = -divisor
        digits = digits[1:]
    
    number = 0
    for digit in digits:
        value = alphabet.find(digit)
        if value < 0:
            raise ValueError("Invalid d64 value: {}".format(value))
        number = (number * 64) + value
    
    return number / divisor


def pos_to_id64(x, y, z):
    return coord_to_d64(x) + ':' + coord_to_d64(y) + ':' + coord_to_d64(z)


def id64_to_pos(id64):
    (x64, y64, z64) = id64.split(':')
    return (d64_to_coord(x64), d64_to_coord(y64), d64_to_coord(z64))


if __name__ == "__main__":
    test1 = ( 51.5625,32.1875,-27.125 )
    test2 = ( -154.65625,40.34375,-82.78125 )
    
    id64 = pos_to_id64(test1[0], test1[1], test1[2])
    print("id64 of {} = {}".format(test1, id64))
    pos = id64_to_pos(id64)
    print("pos of {} = {}".format(id64, pos))
    
    id64 = pos_to_id64(test1[0], test1[1], test1[2])
    print("id64 of {} = {}".format(test1, id64))
    pos = id64_to_pos(id64)
    print("pos of {} = {}".format(id64, pos))
    
    id64 = pos_to_id64(test2[0], test2[1], test2[2])
    print("id64 of {} = {}".format(test2, id64))
    pos = id64_to_pos(id64)
    print("pos of {} = {}".format(id64, pos))
