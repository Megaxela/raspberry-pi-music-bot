def choose_multiplication(
    number: int,
    word_for_single: str,
    word_for_dual: str,
    word_for_multiple: str,
):
    last_symbol = str(number)[-1]
    if last_symbol == "1":
        return word_for_single
    if last_symbol == "2":
        return word_for_dual
    if last_symbol == "3":
        return word_for_dual
    return word_for_multiple


def shorten_to_message(s: str) -> str:
    # technically it's 58, but different symbols has different length.
    # 'Щ' is widest one (wider than '@' and 'W')
    max_line_len = 30
    end_of_str = "..."

    if len(s) <= max_line_len:  # 58 is max amount of symbols in single line
        return s
    return f"{s[:max_line_len - len(end_of_str)]}{end_of_str}"


def time_to_seconds(time: str) -> int:
    try:
        multipliers = [1, 60, 60 * 60, 60 * 60 * 24]
        components = reversed(time.split(":"))

        summ = 0
        multiplier_index = 0

        for component in components:
            component_int = int(component)
            summ += multipliers[multiplier_index] * component_int
            multiplier_index += 1
        return summ
    except (ValueError, IndexError):
        raise ValueError(f'"{time}" is not a time')


def seconds_to_time(seconds: int) -> str:
    hours_total = seconds // 60 // 60
    minutes_total = seconds // 60
    seconds_total = seconds

    hours = hours_total
    minutes = minutes_total - hours * 60
    seconds = seconds_total - minutes_total * 60

    if hours == 0:
        return f"{minutes:02}:{seconds:02}"
    return f"{hours}:{minutes:02}:{seconds:02}"
