# Copyright (C) 2018 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utilities for producing help strings for use in Fire CLIs.

Can produce help strings suitable for display in Fire CLIs for any type of
Python object, module, class, or function.

There are two types of informative strings: Usage and Help screens.

Usage screens are shown when the user accesses a group or accesses a command
without calling it. A Usage screen shows information about how to use that group
or command. Usage screens are typically short and show the minimal information
necessary for the user to determine how to proceed.

Help screens are shown when the user requests help with the help flag (--help).
Help screens are shown in a less-style console view, and contain detailed help
information.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import inspect

from fire import completion
from fire import decorators
from fire import formatting
from fire import inspectutils
from fire import value_types


def HelpText(component, trace=None, verbose=False):
  """Gets the help string for the current component, suitalbe for a help screen.

  Args:
    component: The component to construct the help string for.
    trace: The Fire trace of the command so far. The command executed so far
      can be extracted from this trace.
    verbose: Whether to include private members in the help screen.

  Returns:
    The full help screen as a string.
  """
  # Preprocessing needed to create the sections:
  info = inspectutils.Info(component)
  actions_grouped_by_kind = _GetActionsGroupedByKind(component, verbose=verbose)
  spec = inspectutils.GetFullArgSpec(component)
  metadata = decorators.GetMetadata(component)

  # Sections:
  name_section = _NameSection(info, trace=trace, verbose=verbose)
  synopsis_section = _SynopsisSection(
      component, actions_grouped_by_kind, spec, metadata, trace=trace)
  description_section = _DescriptionSection(info)
  # TODO(dbieber): Add returns and raises sections for functions.

  if inspect.isroutine(component) or inspect.isclass(component):
    # For functions (ARGUMENTS / POSITIONAL ARGUMENTS, FLAGS)
    args_and_flags_sections, notes_sections = _ArgsAndFlagsSections(
        info, spec, metadata)
    usage_details_sections = []
  else:
    # For objects (GROUPS, COMMANDS, VALUES, INDEXES)
    # TODO(dbieber): Show callable function usage in help text.
    args_and_flags_sections = []
    notes_sections = []
    usage_details_sections = _UsageDetailsSections(component,
                                                   actions_grouped_by_kind)

  sections = (
      [name_section, synopsis_section, description_section]
      + args_and_flags_sections
      + usage_details_sections
      + notes_sections
  )
  return '\n\n'.join(
      _CreateOutputSection(*section)
      for section in sections if section is not None
  )


def _NameSection(info, trace=None, verbose=False):
  """The "Name" section of the help string."""
  # Only include separators in the name in verbose mode.
  current_command = _GetCurrentCommand(trace, include_separators=verbose)
  summary = _GetSummary(info)

  if summary:
    text = current_command + ' - ' + summary
  else:
    text = current_command
  return ('NAME', text)


def _SynopsisSection(component, actions_grouped_by_kind, spec, metadata,
                     trace=None):
  """The "Synopsis" section of the help string."""
  current_command = _GetCurrentCommand(trace=trace, include_separators=True)

  # TODO(dbieber): Support callable functions.
  if inspect.isroutine(component) or inspect.isclass(component):
    # For function:
    args_and_flags = _GetArgsAndFlagsString(spec, metadata)
    synopsis_section_template = '{current_command} {args_and_flags}'
    text = synopsis_section_template.format(
        current_command=current_command, args_and_flags=args_and_flags)

  else:
    # For object:
    possible_actions_string = _GetPossibleActionsString(actions_grouped_by_kind)
    synopsis_template = '{current_command} {possible_actions}'
    text = synopsis_template.format(
        current_command=current_command,
        possible_actions=possible_actions_string)

  return ('SYNOPSIS', text)


def _DescriptionSection(info):
  """The "Description" sections of the help string."""
  summary = _GetSummary(info)
  description = _GetDescription(info)
  # Returns the description if available. If not, returns the summary.
  # If neither are available, returns None.
  text = description or summary or None
  if text:
    return ('DESCRIPTION', text)
  else:
    return None


def _ArgsAndFlagsSections(info, spec, metadata):
  """The "Args and Flags" sections of the help string."""
  args_with_no_defaults = spec.args[:len(spec.args) - len(spec.defaults)]
  args_with_defaults = spec.args[len(spec.args) - len(spec.defaults):]
  flags = args_with_defaults + spec.kwonlyargs

  # Check if positional args are allowed. If not, require flag syntax for args.
  accepts_positional_args = metadata.get(decorators.ACCEPTS_POSITIONAL_ARGS)

  args_and_flags_sections = []
  notes_sections = []

  docstring_info = info['docstring_info']

  arg_items = [
      _CreateArgItem(arg, docstring_info)
      for arg in args_with_no_defaults
  ]
  if arg_items:
    title = 'POSITIONAL ARGUMENTS' if accepts_positional_args else 'ARGUMENTS'
    arguments_section = (title, '\n'.join(arg_items).rstrip('\n'))
    args_and_flags_sections.append(arguments_section)
    if accepts_positional_args:
      notes_sections.append(
          ('NOTES', 'You can also use flags syntax for POSITIONAL ARGUMENTS')
      )

  flag_items = [
      _CreateFlagItem(flag, docstring_info)
      for flag in flags
  ]

  if flag_items:
    flags_section = ('FLAGS', '\n'.join(flag_items))
    args_and_flags_sections.append(flags_section)

  return args_and_flags_sections, notes_sections


def _UsageDetailsSections(component, actions_grouped_by_kind):
  """The usage details sections of the help string."""
  groups, commands, values, indexes = actions_grouped_by_kind

  usage_details_sections = []

  if groups:
    usage_details_section = _GroupUsageDetailsSection(groups)
    usage_details_sections.append(usage_details_section)
  if commands:
    usage_details_section = _CommandUsageDetailsSection(commands)
    usage_details_sections.append(usage_details_section)
  if values:
    usage_details_section = _ValuesUsageDetailsSection(component, values)
    usage_details_sections.append(usage_details_section)
  if indexes:
    usage_details_sections.append(
        ('INDEXES', _NewChoicesSection('INDEX', [indexes])))

  return usage_details_sections


def _GetSummary(info):
  docstring_info = info['docstring_info']
  return docstring_info.summary if docstring_info.summary else None


def _GetDescription(info):
  docstring_info = info['docstring_info']
  return docstring_info.description if docstring_info.description else None


def _GetArgsAndFlagsString(spec, metadata):
  """The args and flags string for showing how to call a function.

  If positional arguments are accepted, the args will be shown as positional.
  E.g. "ARG1 ARG2 [--flag=FLAG]"

  If positional arguments are disallowed, the args will be shown with flags
  syntax.
  E.g. "--arg1=ARG1 [--flag=FLAG]"

  Args:
    spec: The full arg spec for the component to construct the args and flags
      string for.
    metadata: Metadata for the component, including whether it accepts
      positional arguments.

  Returns:
    The constructed args and flags string.
  """
  args_with_no_defaults = spec.args[:len(spec.args) - len(spec.defaults)]
  args_with_defaults = spec.args[len(spec.args) - len(spec.defaults):]
  flags = args_with_defaults + spec.kwonlyargs

  # Check if positional args are allowed. If not, require flag syntax for args.
  accepts_positional_args = metadata.get(decorators.ACCEPTS_POSITIONAL_ARGS)

  arg_and_flag_strings = []
  if args_with_no_defaults:
    if accepts_positional_args:
      arg_strings = [formatting.Underline(arg.upper())
                     for arg in args_with_no_defaults]
    else:
      arg_strings = [
          '--{arg}={arg_upper}'.format(
              arg=arg, arg_upper=formatting.Underline(arg.upper()))
          for arg in args_with_no_defaults]
    arg_and_flag_strings.extend(arg_strings)

  flag_string_template = '[--{flag_name}={flag_name_upper}]'
  if flags:
    for flag in flags:
      flag_string = flag_string_template.format(
          flag_name=formatting.Underline(flag),
          flag_name_upper=flag.upper())
      arg_and_flag_strings.append(flag_string)
  return ' '.join(arg_and_flag_strings)


def _GetPossibleActionsString(actions_grouped_by_kind):
  """A help screen string listing the possible action kinds available."""
  groups, commands, values, indexes = actions_grouped_by_kind

  possible_actions = []
  if groups:
    possible_actions.append('GROUP')
  if commands:
    possible_actions.append('COMMAND')
  if values:
    possible_actions.append('VALUE')
  if indexes:
    possible_actions.append('INDEX')

  possible_actions_string = ' | '.join(
      formatting.Underline(action) for action in possible_actions)
  return possible_actions_string


def _GetActionsGroupedByKind(component, verbose=False):
  """Gets lists of available actions, grouped by action kind."""
  groups = []
  commands = []
  values = []

  members = completion._Members(component, verbose)  # pylint: disable=protected-access
  for member_name, member in members:
    member_name = str(member_name)
    if value_types.IsGroup(member):
      groups.append((member_name, member))
    if value_types.IsCommand(member):
      commands.append((member_name, member))
    if value_types.IsValue(member):
      values.append((member_name, member))

  indexes = None
  if isinstance(component, (list, tuple)) and component:
    component_len = len(component)
    # WARNING: Note that indexes is a string, whereas the rest are lists.
    if component_len < 10:
      indexes = ', '.join(str(x) for x in range(component_len))
    else:
      indexes = '0..{max}'.format(max=component_len-1)

  return groups, commands, values, indexes


def _GetCurrentCommand(trace=None, include_separators=True):
  """Returns current command for the purpose of generating help text."""
  if trace:
    current_command = trace.GetCommand(include_separators=include_separators)
  else:
    current_command = ''
  return current_command


def _CreateOutputSection(name, content):
  return """{name}
{content}""".format(name=formatting.Bold(name),
                    content=formatting.Indent(content, 4))


def _CreateArgItem(arg, docstring_info):
  """Returns a string describing a positional argument.

  Args:
    arg: The name of the positional argument.
    docstring_info: A docstrings.DocstringInfo namedtuple with information about
      the containing function's docstring.
  Returns:
    A string to be used in constructing the help screen for the function.
  """
  description = None
  if docstring_info.args:
    for arg_in_docstring in docstring_info.args:
      if arg_in_docstring.name == arg:
        description = arg_in_docstring.description

  arg = arg.upper()
  if description:
    return _CreateItem(formatting.BoldUnderline(arg), description, indent=4)
  else:
    return formatting.BoldUnderline(arg)


def _CreateFlagItem(flag, docstring_info):
  """Returns a string describing a flag using information from the docstring.

  Args:
    flag: The name of the flag.
    docstring_info: A docstrings.DocstringInfo namedtuple with information about
      the containing function's docstring.
  Returns:
    A string to be used in constructing the help screen for the function.
  """
  description = None
  if docstring_info.args:
    for arg_in_docstring in docstring_info.args:
      if arg_in_docstring.name == flag:
        description = arg_in_docstring.description
        break

  flag = '--{flag}'.format(flag=formatting.Underline(flag))
  if description:
    return _CreateItem(flag, description, indent=2)
  return flag


def _CreateItem(name, description, indent=2):
  return """{name}
{description}""".format(name=name,
                        description=formatting.Indent(description, indent))


def _GroupUsageDetailsSection(groups):
  """Creates a section tuple for the groups section of the usage details."""
  group_item_strings = []
  for group_name, group in groups:
    group_info = inspectutils.Info(group)
    group_item = group_name
    if 'docstring_info' in group_info:
      group_docstring_info = group_info['docstring_info']
      if group_docstring_info and group_docstring_info.summary:
        group_item = _CreateItem(group_name,
                                 group_docstring_info.summary)
    group_item_strings.append(group_item)
  return ('GROUPS', _NewChoicesSection('GROUP', group_item_strings))


def _CommandUsageDetailsSection(commands):
  """Creates a section tuple for the commands section of the usage details."""
  command_item_strings = []
  for command_name, command in commands:
    command_info = inspectutils.Info(command)
    command_item = command_name
    if 'docstring_info' in command_info:
      command_docstring_info = command_info['docstring_info']
      if command_docstring_info and command_docstring_info.summary:
        command_item = _CreateItem(command_name,
                                   command_docstring_info.summary)
    command_item_strings.append(command_item)
  return ('COMMANDS', _NewChoicesSection('COMMAND', command_item_strings))


def _ValuesUsageDetailsSection(component, values):
  """Creates a section tuple for the values section of the usage details."""
  value_item_strings = []
  for value_name, value in values:
    del value
    init_info = inspectutils.Info(component.__class__.__init__)
    value_item = None
    if 'docstring_info' in init_info:
      init_docstring_info = init_info['docstring_info']
      if init_docstring_info.args:
        for arg_info in init_docstring_info.args:
          if arg_info.name == value_name:
            value_item = _CreateItem(value_name, arg_info.description)
    if value_item is None:
      value_item = str(value_name)
    value_item_strings.append(value_item)
  return ('VALUES', _NewChoicesSection('VALUE', value_item_strings))


def _NewChoicesSection(name, choices):
  return _CreateItem(
      '{name} is one of the following:'.format(
          name=formatting.Bold(formatting.Underline(name))),
      '\n' + '\n\n'.join(choices),
      indent=1)


def UsageText(component, trace=None, verbose=False):
  if inspect.isroutine(component) or inspect.isclass(component):
    return UsageTextForFunction(component, trace, verbose)
  else:
    return UsageTextForObject(component, trace, verbose)


def UsageTextForFunction(component, trace=None, verbose=False):
  """Returns usage text for function objects.

  Args:
    component: The component to determine the usage text for.
    trace: The Fire trace object containing all metadata of current execution.
    verbose: Whether to display the usage text in verbose mode.

  Returns:
    String suitable for display in an error screen.
  """
  del verbose  # Unused.

  output_template = """Usage: {current_command} {args_and_flags}
{availability_lines}
For detailed information on this command, run:
  {current_command}{hyphen_hyphen} --help"""

  if trace:
    command = trace.GetCommand()
    needs_separating_hyphen_hyphen = trace.NeedsSeparatingHyphenHyphen()
  else:
    command = None
    needs_separating_hyphen_hyphen = False

  if not command:
    command = ''

  spec = inspectutils.GetFullArgSpec(component)
  args = spec.args
  if spec.defaults is None:
    num_defaults = 0
  else:
    num_defaults = len(spec.defaults)
  args_with_no_defaults = args[:len(args) - num_defaults]
  args_with_defaults = args[len(args) - num_defaults:]
  flags = args_with_defaults + spec.kwonlyargs

  # Check if positional args are allowed. If not, show flag syntax for args.
  metadata = decorators.GetMetadata(component)
  accepts_positional_args = metadata.get(decorators.ACCEPTS_POSITIONAL_ARGS)
  if not accepts_positional_args:
    items = ['--{arg}={upper}'.format(arg=arg, upper=arg.upper())
             for arg in args_with_no_defaults]
  else:
    items = [arg.upper() for arg in args_with_no_defaults]

  if flags:
    items.append('<flags>')
    availability_lines = (
        '\nAvailable flags: '
        + ' | '.join('--' + flag for flag in flags) + '\n')
  else:
    availability_lines = ''
  args_and_flags = ' '.join(items)

  hyphen_hyphen = ' --' if needs_separating_hyphen_hyphen else ''

  return output_template.format(
      current_command=command,
      args_and_flags=args_and_flags,
      availability_lines=availability_lines,
      hyphen_hyphen=hyphen_hyphen)


def UsageTextForObject(component, trace=None, verbose=False):
  """Returns the usage text for the error screen for an object.

  Constructs the usage text for the error screen to inform the user about how
  to use the current component.

  Args:
    component: The component to determine the usage text for.
    trace: The Fire trace object containing all metadata of current execution.
    verbose: Whether to include private members in the usage text.
  Returns:
    String suitable for display in error screen.
  """
  output_template = """Usage: {current_command}{possible_actions}
{availability_lines}
For detailed information on this command, run:
  {current_command} --help"""
  if trace:
    command = trace.GetCommand()
  else:
    command = None

  if not command:
    command = ''

  actions_grouped_by_kind = _GetActionsGroupedByKind(component, verbose=verbose)
  groups, commands, values, indexes = actions_grouped_by_kind

  possible_actions = []
  availability_lines = []
  if groups:
    possible_actions.append('group')
    groups_text = _CreateAvailabilityLine(
        header='available groups:',
        items=groups)
    availability_lines.append(groups_text)
  if commands:
    possible_actions.append('command')
    commands_text = _CreateAvailabilityLine(
        header='available commands:',
        items=commands)
    availability_lines.append(commands_text)
  if values:
    possible_actions.append('value')
    values_text = _CreateAvailabilityLine(
        header='available values:',
        items=values)
    availability_lines.append(values_text)
  if indexes:
    possible_actions.append('index')
    indexes_text = _CreateAvailabilityLine(
        header='available indexes:',
        items=[(indexes, None)])
    availability_lines.append(indexes_text)

  if possible_actions:
    possible_actions_string = ' <{actions}>'.format(
        actions='|'.join(possible_actions))
  else:
    possible_actions_string = ''

  availability_lines_string = ''.join(availability_lines)

  return output_template.format(
      current_command=command,
      possible_actions=possible_actions_string,
      availability_lines=availability_lines_string)


def _CreateAvailabilityLine(header, items,
                            header_indent=2, items_indent=25, line_length=80):
  items_width = line_length - items_indent
  item_names = [item[0] for item in items]
  items_text = '\n'.join(formatting.WrappedJoin(item_names, width=items_width))
  indented_items_text = formatting.Indent(items_text, spaces=items_indent)
  indented_header = formatting.Indent(header, spaces=header_indent)
  return indented_header + indented_items_text[len(indented_header):] + '\n'
