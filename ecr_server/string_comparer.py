import sys
import datetime
from itertools import zip_longest


def postprocess_string(s):
    return s.lower().strip()


def log_equal_strings(string1, string2):
    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"{current_datetime}: {string1} is equal to {string2}\n"
    with open("comparison_log.txt", "a") as log_file:
        log_file.write(log_message)


def log_different_strings(string1, string2, position, char1, char2):
    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"{current_datetime}: {string1} is not equal to {string2}, at position {position} first string has char {char1} ({ord(char1)}), second has char {char2} ({ord(char2)})\n"
    with open("comparison_log.txt", "a") as log_file:
        log_file.write(log_message)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python compare_strings.py <string1> <string2>")
        sys.exit(1)

    string1 = postprocess_string(sys.argv[1])
    string2 = postprocess_string(sys.argv[2])

    if string1 == string2:
        print("Same!")
        log_equal_strings(string1, string2)
        sys.exit(0)
    else:
        print("Different!")
        for position, (char1, char2) in enumerate(zip_longest(string1, string2, fillvalue=' '), start=1):
            if char1 != char2:
                log_different_strings(string1, string2, position, char1, char2)
                break
        sys.exit(1)
