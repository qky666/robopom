import click
import robopom.cli.cli as cli


@click.command(name="template")
def template_command() -> None:
    """
    Generate project skeleton in current directory.
    """
    click.echo("Creating template files...")
    cli.template()
    click.echo("Done")


if __name__ == '__main__':
    template_command()
