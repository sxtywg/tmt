import dataclasses
from typing import TYPE_CHECKING, Any, List, Optional, Type, Union, cast

import click

import tmt
import tmt.steps
from tmt.steps import Action

if TYPE_CHECKING:
    import tmt.cli


@dataclasses.dataclass
class ReportStepData(tmt.steps.StepData):
    pass


class ReportPlugin(tmt.steps.GuestlessPlugin):
    """ Common parent of report plugins """

    _data_class = ReportStepData

    # Default implementation for report is display
    how = 'display'

    # List of all supported methods aggregated from all plugins of the same step.
    _supported_methods: List[tmt.steps.Method] = []

    @classmethod
    def base_command(
            cls,
            usage: str,
            method_class: Optional[Type[click.Command]] = None) -> click.Command:
        """ Create base click command (common for all report plugins) """

        # Prepare general usage message for the step
        if method_class:
            usage = Report.usage(method_overview=usage)

        # Create the command
        @click.command(cls=method_class, help=usage)
        @click.pass_context
        @click.option(
            '-h', '--how', metavar='METHOD',
            help='Use specified method for results reporting.')
        def report(context: 'tmt.cli.Context', **kwargs: Any) -> None:
            context.obj.steps.add('report')
            Report._save_context(context)

        return report


class Report(tmt.steps.Step):
    """ Provide test results overview and send reports. """

    # Default implementation for report is display
    DEFAULT_HOW = 'display'

    _plugin_base_class = ReportPlugin

    def wake(self) -> None:
        """ Wake up the step (process workdir and command line) """
        super().wake()

        # Choose the right plugin and wake it up
        for data in self.data:
            # FIXME: cast() - see https://github.com/teemtee/tmt/issues/1599
            plugin = cast(ReportPlugin, ReportPlugin.delegate(self, data=data))
            plugin.wake()
            self._phases.append(plugin)

        # Nothing more to do if already done
        if self.status() == 'done':
            self.debug(
                'Report wake up complete (already done before).', level=2)
        # Save status and step data (now we know what to do)
        else:
            self.status('todo')
            self.save()

    def summary(self) -> None:
        """ Give a concise report summary """
        summary = tmt.result.Result.summary(self.plan.execute.results())
        self.info('summary', summary, 'green', shift=1)

    def go(self) -> None:
        """ Report the guests """
        super().go()

        # Nothing more to do if already done
        if self.status() == 'done':
            self.info('status', 'done', 'green', shift=1)
            self.summary()
            self.actions()
            return

        # Perform the reporting
        for phase in self.phases(classes=(Action, ReportPlugin)):
            # TODO: I don't understand this, but mypy seems to be confused about the type
            # of `phase`. Mypy in my Code reports correct `Action | ReportPlugin` union,
            # but pre-commit's mypy sees `Phase` - which should not be the right answer
            # since `classes` is clearly not `None`. Adding `cast()` to overcome this
            # because I can't find the actual error :/
            cast(Union[Action, ReportPlugin], phase).go()

        # Give a summary, update status and save
        self.summary()
        self.status('done')
        self.save()
