import click
import robopom.cli.template as template


@click.group(name="robopom")
def robopom_command() -> None:
    """
    robopom command.
    """
    pass


def robopom_entry() -> None:
    robopom_command.add_command(template.template_command)
    robopom_command()


if __name__ == '__main__':
    robopom_entry()
