from argparse import ArgumentParser, HelpFormatter

from pkg_name.color import Color


class CustomHelpFormatter(HelpFormatter):
    """Inherits argparse.HelpFormatter

    Args:
        HelpFormatter (class): argparse.HelpFormatter
    """
    def __init__(self, prog, indent_increment=2, max_help_position=24, width=100, color='cyan'):
        """Initializes CustomHelpFormatter class, a class to create a custom help output to the terminal.
        Inherits argparse.HelpFormatter

        Args:
            prog (str): the name of the program.
            indent_increment (int, optional): indent space. Defaults to 2.
            max_help_position (int, optional): max help position. Defaults to 24.
            width (int, optional): width. Defaults to 100.
            color (str, optional): color to display the option arguments. Defaults to 'cyan'.
        """
        super().__init__(prog, indent_increment, max_help_position, width)
        self.color = color

    def _format_action(self, action):
        """Adds color and adds a line space between each argument for better readability

        Args:
            action (str): option argument text

        Returns:
            str: formatted option argument
        """
        return Color().format_message(f'{super()._format_action(action)}\n', self.color, _format='italic')


class ArgParser(ArgumentParser):
    """Inherits argparse.ArgumentParser

    Args:
        ArgumentParser (class): argparse.ArgumentParser
    """
    def __init__(self, description='Arg Parser', parent_args: list = None, create_arguments: dict = None,
                 help_color='yellow'):
        """Initializes ArgParser class. Inherits argparse.ArgumentParser and sets custom formatter_class to
        CustomHelpFormatter

        Args:
            description (str): Help description. Defaults to 'Arg Parser'
            create_arguments (dict, optional): Arguments to create. Defaults to {}.
            help_color (str, optional): terminal color of help header. Defaults to 'yellow'.
        """
        super().__init__(formatter_class=CustomHelpFormatter, description=description)
        self.args = {}
        self.parent_args = parent_args or []
        self.create_arguments = create_arguments or {}
        self.help_color = help_color

    def format_help(self):
        """Overrides argparse.ArgumentParser.format_help to add color to the command line header to the color set to
        self.help_color

        Returns:
            str: color formatted string
        """
        return Color().format_message(super().format_help(), self.help_color)

    def create_argument(self, arg_name: str, short_name: str = None, **kwargs):
        """Instead of creating one large dict and setting self.create_arguments, each entry can be passed here and
        self.create_arguments will be populated with the data.

        Args:
            arg_name (str): argument name
            short_name (str, optional): Short name of argument. Defaults to None.

        Returns:
            bool: True on success, False otherwise
        """
        arg_name = self.__handle_arg_name(arg_name)
        if arg_name:
            if short_name:
                kwargs['short_name'] = short_name
            self.__handle_arg_shortname(kwargs, False)
            return self.__add_create_argument(arg_name, kwargs)
        return False

    def __add_create_argument(self, arg_name: str, arg_values: dict):
        """Helper function to actually set self.create_arguments dict with key/value

        Args:
            arg_name (str): name of argument
            arg_values (dict): argument config

        Returns:
            bool: True on success, False otherwise
        """
        try:
            self.create_arguments[arg_name] = arg_values
            return True
        except Exception as error:
            print(f'Failed to add argument to create_arguments: {error}')
        return False

    def set_arguments(self):
        """Loops through create_arguments dict and adds each entry data to argparse.ArgumentParser.add_argument

        Returns:
            dict: dictionary containing all added args from create_arguments on success. Exits 1 on failure
        """
        for arg_name, arg_values in self.create_arguments.items():
            arg_name = self.__handle_arg_name(arg_name)
            short_name = self.__handle_arg_shortname(arg_values)
            if arg_name:
                if not self.__handle_adding_arg(short_name, arg_name, arg_values):
                    exit(1)
        return self.__parse_set_args()

    def __parse_set_args(self):
        """Runs argparse.ArgumentParser.parse_args and sets self.args with the vars() output to convert object to dict

        Returns:
            dict: dictionary of vars(argparse.ArgumentParser.parse_args) on success. Exits 1 on failure
        """
        try:
            if self.parent_args:
                self.args = vars(self.parse_args(self.parent_args))
            else:
                self.args = vars(self.parse_args())
            return self.args
        except Exception as error:
            print(f'Failed to parse args: {error}')
            exit(1)

    def __handle_arg_name(self, arg_name: str):
        """Filters arg name (self.create_arguments dict key) to appropriate formatting

        Args:
            arg_name (str): name of the argument (Long name)

        Returns:
            str: Filtered arg name
        """
        try:
            arg_name.replace(' ', '_')
            if not arg_name.startswith('--'):
                if arg_name[0] == '-':
                    return f'-{arg_name}'
                return f'--{arg_name}'
            return arg_name
        except Exception as error:
            print(f'Failed to handle arg name: {error}')
            exit(1)

    def __handle_arg_shortname(self, arg_values: dict, delete_short_name: bool = True):
        """Filters the optional short arg name to appropriate formatting

        Args:
            arg_values (dict): arg values of argument
            delete_short_name (bool, optional): Specifies if the short name should be removed from arg values.
            Defaults to True.

        Returns:
            str|None: Filtered short arg name or None on failure or if a short name was not provided.
        """
        try:
            short_name = str(arg_values.get('short', ''))
            if short_name:
                if delete_short_name:
                    del arg_values['short']
                if short_name.startswith('-'):
                    if short_name[1] == '-':
                        return short_name[1:]
                    return short_name
                return f'-{short_name}'
        except Exception as error:
            print(f'Failed to handle short name: {error}')
        return None

    def __handle_adding_arg(self, short_name: str, arg_name: str, arg_values: dict):
        """Adds argument to argparse.ArgumentParser.add_argument

        Args:
            short_name (str): short name for argument. Example: '-h' for '--help' long arg name
            arg_name (str): arg name (long name)
            arg_values (dict): values for argument

        Returns:
            bool: True on success, False otherwise
        """
        try:
            if short_name:
                self.add_argument(short_name, arg_name, **arg_values)
            else:
                self.add_argument(arg_name, **arg_values)
            return True
        except Exception as error:
            print(f'Failed to add argument: {error}')
        return False
