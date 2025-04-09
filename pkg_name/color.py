class Color:

    @property
    def colors(self) -> dict:
        """Possible color options for foreground and background

        Returns:
            dict: color options
        """
        return {
            'foreground': {
                'black': '30m',
                'red': '31m',
                'green': '32m',
                'yellow': '33m',
                'blue': '34m',
                'magenta': '35m',
                'cyan': '36m',
                'white': '37m',
                'bright-black': '90m',
                'bright-red': '91m',
                'bright-green': '92m',
                'bright-yellow': '93m',
                'bright-blue': '94m',
                'bright-magenta': '95m',
                'bright-cyan': '96m',
                'bright-white': '97m'
            },
            'background': {
                'black': '40m',
                'red': '41m',
                'green': '42m',
                'yellow': '43m',
                'blue': '44m',
                'magenta': '45m',
                'cyan': '46m',
                'white': '47m',
                'bright-black': '100m',
                'bright-red': '101m',
                'bright-green': '102m',
                'bright-yellow': '103m',
                'bright-blue': '104m',
                'bright-magenta': '105m',
                'bright-cyan': '106m',
                'bright-white': '107m'
            }
        }

    @property
    def formatting(self) -> dict:
        """Possible formatting options

        Returns:
            dict: formatting options
        """
        return {
            'reset': '00m',
            'default': '10m',
            'bold': '01m',
            'dim': '02m',
            'italic': '03m',
            'underline': '04m',
            'double-underline': '21m',
            'slow-blink': '05m',
            'rapid-blink': '06m',
            'invert': '07m',
            'hide': '08m',
            'strike': '09m'
        }

    @property
    def esc(self) -> str:
        """Escape character

        Returns:
            str: escape character
        """
        return '\033['

    @property
    def reset(self) -> str:
        """Reset formatting

        Returns:
            str: reset formatting
        """
        return f'{self.esc}{self.formatting["reset"]}'

    def __build_format(self, _format: str = 'default'):
        """Build formatting string

        Args:
            _format (str, optional): formatting option. Defaults to 'default'.

        Returns:
            str: formatted string
        """
        try:
            return f'{self.esc}{self.formatting[_format]}'
        except KeyError:
            print(f'Failed to get formatting using key: {_format}')
        return ''

    def __build_color(self, color: str, ground: str = 'foreground') -> str:
        """Build color string

        Args:
            color (str): color option
            ground (str, optional): ground option (foreground or background). Defaults to 'foreground'.

        Returns:
            str: color string
        """
        try:
            return f'{self.esc}{self.colors[ground][color]}'
        except KeyError:
            print(f'Failed to get color format using keys: {ground}, {color}')
        return ''

    def print_message(self, msg: str, color: str, ground: str = 'foreground', _format: str = 'default'):
        """Print formatted message

        Args:
            msg (str): message to print to console
            color (str): color the message should be
            ground (str, optional): the formatting ground (foreground, background). Defaults to 'foreground'.
            _format (str, optional): formatting options. Defaults to 'default'.
        """
        print(self.format_message(msg, color, ground, _format))

    def format_message(self, msg: str, color: str, ground: str = 'foreground', _format: str = 'default') -> str:
        """Format message with color and formatting

        Args:
            msg (str): message to print to console
            color (str): color the message should be
            ground (str, optional): the formatting ground (foreground, background). Defaults to 'foreground'.
            _format (str, optional): formatting options. Defaults to 'default'.

        Returns:
            str: formatted message
        """
        return f'{self.__build_color(color, ground)}{self.__build_format(_format)}{msg}{self.reset}'
