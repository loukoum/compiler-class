#!/usr/bin/env python3
#Karantias Konstantinos 2454 cse32454 Goulioumis Ioannis 2232 cse32232
import argparse
import os
import re
import sys
from collections import defaultdict, namedtuple
from pprint import pformat

INVALID_TOKENS = [
    (
        'ccomment', re.compile(r'\A\*\/')
    ),  # should normally be consumed via IGNORED_TOKENS's comment, otherwise there was no comment open
    ('unshut_comment', re.compile(r'\A/\*((?!\*/).)*\Z', re.DOTALL)),
]

IGNORED_TOKENS = [
    ('whitespace', re.compile(r'\A\s+')),
    ('comment', re.compile(r'\A/\*((?!\*/).)*\*/', re.DOTALL)),
    ('inline_comment', re.compile(r'\A//.*')),
]

SINGLE_WORD_TOKENS = ('program', 'endprogram', 'declare', 'enddeclare', 'if',
                      'then', 'else', 'endif', 'while', 'endwhile', 'repeat',
                      'endrepeat', 'exit', 'switch', 'case', 'endswitch',
                      'forcase', 'when', 'endforcase', 'procedure',
                      'endprocedure', 'function', 'endfunction', 'call',
                      'return', 'in', 'inout', 'and', 'or', 'not', 'true',
                      'false', 'input', 'print')

VALID_TOKENS = [
    (word, re.compile(r'\A\b' + re.escape(word) + r'\b'))
    for word in SINGLE_WORD_TOKENS
] + [('assign', re.compile(r'\A:=')), ('semicolon', re.compile(r'\A;')),
     ('colon', re.compile(r'\A:')), ('comma', re.compile(r'\A,')),
     ('id', re.compile(r'\A([a-zA-Z][a-zA-Z0-9]{0,29})[a-zA-Z0-9]*')),
     ('int', re.compile(r'\A\b\d+\b')), ('plus', re.compile(r'\A\+')),
     ('minus', re.compile(r'\A-')), ('div', re.compile(r'\A/')),
     ('mul', re.compile(r'\A\*')), ('oparen', re.compile(r'\A\(')),
     ('cparen', re.compile(r'\A\)')), ('obracket', re.compile(r'\A\[')),
     ('cbracket', re.compile(r'\A\]')), ('neq', re.compile(r'\A<>')),
     ('ge', re.compile(r'\A>=')), ('le', re.compile(r'\A<=')),
     ('gt', re.compile(r'\A>')), ('lt', re.compile(r'\A<')),
     ('eq', re.compile(r'\A='))]

EXTRA_VALIDATORS = defaultdict(lambda: lambda x: True)
EXTRA_VALIDATORS['int'] = lambda x: -32767 <= int(x) <= 32767

Token = namedtuple('Token', ['type', 'value', 'pos'])


class CompilationError(Exception):
    def __init__(self, pos, msg, suggestion=None):
        self.pos = pos
        self.msg = msg
        self.suggestion = suggestion

    def __str__(self):
        const_part = '(%d,%d):\n\t%s' % (self.pos.row, self.pos.col, self.msg)
        suggestion_part = '\n\t-> %s' % self.suggestion if self.suggestion else ''
        return const_part + suggestion_part


class LexerError(CompilationError):
    pass


class InvalidTokenError(LexerError):
    def get_msg(self, token_type):
        return {
            'unshut_comment': 'A comment starts here that never ends.',
            'ccomment': 'A comment was ended here but it never started.',
        }.get(token_type, 'Invalid token: %s' % token_type)

    def __init__(self, pos, token_type=None):
        super().__init__(pos, msg=self.get_msg(token_type))


class SyntaxAnalyzerError(CompilationError):
    def get_suggestion(self, got_token_type):
        return {
            'id': 'Maybe a ";" or a "," is missing.'
        }.get(got_token_type, None)

    def __init__(self, pos, expected_type, got_token):
        super().__init__(
            pos,
            msg='Expected token of type `%s`, got `%s` (`%s`).' %
            (expected_type, got_token.type, got_token.value),
            suggestion=self.get_suggestion(got_token.type))


class Lexer:
    def advance_from_match(self, match):
        right_of_match = match.span()[1]
        self.cursor.advance(right_of_match)

    def __init__(self, source):
        self.cursor = StringCursor(source)

    def source(self):
        return self.cursor.rest()

    def tokenize(self):
        tokens = []
        while len(self.source()) > 0:
            for name, regex in INVALID_TOKENS:
                match = regex.search(self.source())
                if match:
                    raise InvalidTokenError(
                        pos=self.cursor.position(), token_type=name)

            for name, regex in IGNORED_TOKENS:
                match = regex.search(self.source())
                if match:
                    self.advance_from_match(match)
                    break
            else:
                found_token = False

                for name, regex in VALID_TOKENS:
                    match = regex.search(self.source())
                    if match and EXTRA_VALIDATORS[name](match.group()):
                        found_token = True

                        value = match.group() if len(
                            match.groups()) == 0 else match.group(1)
                        token = Token(
                            type=name, value=value, pos=self.cursor.position())
                        tokens.append(token)
                        self.advance_from_match(match)
                        break

                if not found_token:
                    raise InvalidTokenError(
                        pos=self.cursor.position(),
                        token_type=self.source().split()[0])
        return tokens


class StringCursor:
    def __init__(self, string):
        self.string = string
        self.char_pos = 0  # in chars
        self.pos = CursorPosition(1, 1)

    def advance(self, nchars):
        newline = re.compile(r'\r\n|\r|\n')
        new_char_pos = self.char_pos + nchars

        if new_char_pos > len(self.string):
            raise ValueError(
                'Tried to move past the end of the string `%s`.' % self.rest())

        linebreaks = list(
            newline.finditer(
                self.string, pos=self.char_pos, endpos=new_char_pos))

        inbetween_rows = len(linebreaks)
        row = self.pos.row
        col = self.pos.col
        if inbetween_rows > 0:
            pos_of_current_line_start = linebreaks[-1].span()[1]
            row += inbetween_rows
            col = new_char_pos - pos_of_current_line_start + 1
        else:
            col += nchars

        self.char_pos = new_char_pos
        self.pos = CursorPosition(row, col)

    def rest(self):
        return self.string[self.char_pos:]

    def position(self):
        return self.pos


CursorPosition = namedtuple('CursorPosition', ['row', 'col'])

Quad = namedtuple('quad', ['id', 'op', 'term0', 'term1', 'target'])


class QuadGenerator:
    def __init__(self, table=None):
        self.quad_id = 0
        self.temp_id = 0
        self.quad_list = []
        self.table = table
        self.marked = []

    def nextquad(self):
        return self.quad_id

    def genquad(self, op, term0, term1, target):
        self.quad_list.append(
            Quad(
                id=self.quad_id,
                op=op,
                term0=term0,
                term1=term1,
                target=target))
        self.marked.append(False)
        self.quad_id += 1

    def newtemp(self, should_gen=True):
        temp = 'T_%d' % self.temp_id
        self.temp_id += 1
        if should_gen and self.table is not None:
            self.table.add_entity(TempVariableEntity(temp))
        return temp

    def backpatch(self, lst, target):
        for l in lst:
            quad = self.quad_list[l]
            self.quad_list[l] = Quad(
                id=quad.id,
                op=quad.op,
                term0=quad.term0,
                term1=quad.term1,
                target=target)

    def get_and_mark_quads_from(self, from_index):
        quads = [
            quad for quad in self.quad_list[from_index:]
            if not self.marked[quad.id]
        ]

        for i in range(from_index, len(self.marked)):
            self.marked[i] = True

        return quads

    def __str__(self):
        return '\n'.join(
            '%s: (%s, %s, %s, %s)' % (quad.id, quad.op, quad.term0, quad.term1,
                                      quad.target) for quad in self.quad_list)


class TrueFalse:
    def __init__(self, true=[], false=[]):
        self.true = true
        self.false = false


class Serializable:
    def __repr__(self):
        return pformat(self.__dict__)


class Comparable:
    def __eq__(self, other):
        return self.__dict__ == other.__dict__


class Entity(Serializable, Comparable):
    def __init__(self, name):
        self.name = name

    def is_a_function(self):
        return False

    def is_a_procedure(self):
        return False

    def is_a_variable(self):
        return False


class VariableEntity(Entity):
    def __init__(self, name, offset=None):
        super().__init__(name)
        self.offset = offset

    def is_a_variable(self):
        return True


class FunctionEntity(Entity):
    def __init__(self,
                 name,
                 start_quad,
                 arguments=None,
                 frame_length=None,
                 type='function'):
        super().__init__(name)
        self.start_quad = start_quad
        self.arguments = arguments if arguments is not None else []
        self.frame_length = frame_length
        self.type = type

    def is_a_function(self):
        return self.type == 'function'

    def is_a_procedure(self):
        return self.type == 'procedure'

    def has_signature(self, types):
        expected = [arg.mode for arg in self.arguments]
        return types == expected


class ParameterEntity(Entity):
    def __init__(self, name, mode, offset=None):
        super().__init__(name)
        self.mode = mode
        self.offset = offset

    def is_a_variable(self):
        return True


class TempVariableEntity(Entity):
    def __init__(self, name, offset=None):
        super().__init__(name)
        self.offset = offset

    def is_a_variable(self):
        return True


class Scope(Serializable, Comparable):
    def __init__(self, nesting_level, entities=None):
        self.nesting_level = nesting_level
        self.entities = [] if entities is None else entities


class Argument(Serializable, Comparable):
    def __init__(self, name, mode):
        self.name = name
        self.mode = mode


LookupResult = namedtuple('LookupResult', ['entity', 'nesting_level'])


class SymbolTable:
    def __init__(self):
        self.scopes = []

    def create_scope(self):
        params = []
        if isinstance(self.last_entity(), FunctionEntity):
            params = [
                ParameterEntity(arg.name, arg.mode, 12 + i * 4)
                for i, arg in enumerate(self.last_entity().arguments)
            ]
        self.scopes.append(Scope(len(self.scopes)))
        self.scopes[-1].entities += params

    def destroy_scope(self):
        if not self.is_callee_framelength_filled_in():
            raise Exception
        self.scopes.pop()

    def fill_in_framelength_on_callee(self):
        if self.callee() is None:
            return
        self.callee().frame_length = self.get_current_framelength()

    def is_callee_framelength_filled_in(self):
        if self.callee() is None:
            return True
        return self.callee().frame_length is not None

    def callee(self):
        if len(self.scopes) <= 1:
            return None
        candidate = self.scopes[-2].entities[-1]
        if not isinstance(candidate, FunctionEntity):
            raise Exception
        return candidate

    def add_entity(self, entity):
        if hasattr(entity, 'offset'):
            entity.offset = self.find_closest_on_current_scope_with_offset().offset + 4 \
            if self.find_closest_on_current_scope_with_offset() is not None else 12

        self.scopes[-1].entities.append(entity)

    def find_closest_on_current_scope_with_offset(self):
        for entity in self.scopes[-1].entities[::-1]:
            if hasattr(entity, 'offset') and entity.offset is not None:
                return entity

    def add_argument(self, arg):
        head = self.last_entity()
        if not isinstance(head, FunctionEntity):
            raise ValueError
        head.arguments.append(arg)

    def last_entity(self):
        try:
            return self.scopes[-1].entities[-1]
        except:
            return None

    def am_i_inside_function(self):
        if len(self.scopes) > 1:
            parent_last = self.scopes[-2].entities[-1]
            return isinstance(
                parent_last, FunctionEntity) and parent_last.type == 'function'
        return False

    def lookup(self, name, scopes=None):
        scopes = self.scopes if scopes is None else scopes
        for scope in scopes[::-1]:
            for entity in scope.entities[::-1]:
                try:
                    if entity.name == name:
                        return LookupResult(entity, scope.nesting_level)
                except AttributeError:
                    pass
        return None

    def lookup_on_current_scope(self, name):
        return self.lookup(name, scopes=[self.scopes[-1]])

    def has_an_entity_that_fulfills(self, name, fulfills=lambda x: True):
        lookup_result = self.lookup(name)
        if lookup_result is None:
            return False
        elif fulfills(lookup_result.entity):
            return True
        else:
            return False

    def has_a_variable(self, name):
        return self.has_an_entity_that_fulfills(name,
                                                lambda x: x.is_a_variable())

    def has_a_procedure(self, name):
        return self.has_an_entity_that_fulfills(name,
                                                lambda x: x.is_a_procedure())

    def has_a_function(self, name):
        return self.has_an_entity_that_fulfills(name,
                                                lambda x: x.is_a_function())

    def has_a_callable_with_signature(self, name, sig):
        return self.has_an_entity_that_fulfills(name,
                                                lambda x: x.has_signature(sig))

    def get_current_nesting_level(self):
        return max(0, len(self.scopes) - 1)

    def get_cause_of_birth(self):
        return self.scopes[-2].entities[-1]

    def get_var_entities_on_scope(self, scope):
        var_entities = 0
        for entity in scope.entities:
            if entity.is_a_variable():
                var_entities += 1

        return var_entities

    def get_current_framelength(self):
        return 12 + self.get_var_entities_on_scope(self.scopes[-1]) * 4


class FinalGen:
    def __init__(self, table, quad_gen=None):
        self.table = table
        self.quad_gen = quad_gen
        self.generated = []

    def gnlvcode(self, var):
        ret = []
        ret.append('lw $t0, -4($sp)')
        lookup_res = self.table.lookup(var)

        for i in range(self.table.get_current_nesting_level() -
                       lookup_res.nesting_level):
            ret.append('lw $t0, -4($t0)')

        ret.append('add $t0, $t0, -%d' % lookup_res.entity.offset)
        return ret

    def store_load_rv(self, reg, var, lookup_res, func):
        current_nesting_level = self.table.get_current_nesting_level()
        if lookup_res.nesting_level == 0:
            return [
                '%s $t%s, -%d($s0)' % (func, reg, lookup_res.entity.offset)
            ]
        elif lookup_res.nesting_level == current_nesting_level:
            if isinstance(lookup_res.entity, ParameterEntity) and \
                    lookup_res.entity.mode == 'ref':
                return [
                    'lw $t0, -%d($sp)' % lookup_res.entity.offset,
                    '%s $t%s, ($t0)' % (func, reg)
                ]

            return [
                '%s $t%s, -%d($sp)' % (func, reg, lookup_res.entity.offset)
            ]
        else:
            gnlvret = self.gnlvcode(var)

            if isinstance(lookup_res.entity, ParameterEntity) and \
                    lookup_res.entity.mode == 'ref':
                return gnlvret + [
                    'lw $t0, ($t0)',
                    '%s $t%s, ($t0)' % (func, reg)
                ]

            return gnlvret + ['%s $t%d, ($t0)' % (func, reg)]

    def isconst(self, var):
        try:
            int(var)
            return True
        except ValueError:
            return False

    def loadvr(self, var, reg):
        if self.isconst(var):
            return ['li $t%s, %s' % (reg, var)]

        lookup_res = self.table.lookup(var)
        return self.store_load_rv(reg, var, lookup_res, 'lw')

    def storerv(self, reg, var):
        lookup_res = self.table.lookup(var)
        return self.store_load_rv(reg, var, lookup_res, 'sw')

    def generate_block(self):
        current_level = self.table.get_current_nesting_level()
        if current_level == 0:
            start_quad = 0
        else:
            start_quad = self.table.get_cause_of_birth().start_quad

        quads = self.quad_gen.get_and_mark_quads_from(start_quad)

        par_quads = []
        for i, quad in enumerate(quads):
            if quad.op == 'par':
                par_quads += [quad]
            else:
                if quad.op == 'call':
                    self.generated += self.precall_set_fp(quad.term0)

                if len(par_quads) > 0:
                    self.generated += self.setup_parameters(par_quads)
                    par_quads = []

                self.generated += self.translate_quad(quad)

        if current_level is not 0:
            self.generated += self.jump_to_ra()

    def precall_set_fp(self, func_name):
        lookup_res = self.table.lookup(func_name)
        return ['add $fp, $sp, %s' % lookup_res.entity.frame_length]

    def jump_to_ra(self):
        return ['lw $ra, ($sp)', 'jr $ra']

    def generate_jump_to_main(self):
        self.generated += ['j L_0']

    def generate_program_exit(self, quad_id):
        self.generated += ['L_%s:' % quad_id, 'li $v0, 10', 'syscall']

    def new_scope_setup(self):
        framelength = self.table.get_current_framelength()
        if self.table.get_current_nesting_level() == 0:
            main = ['move $s0, $sp']
        else:
            main = []

        return ['add $sp, $sp, %s' % framelength, 'sw $ra, ($sp)'] + main

    def init_call(self, func_name):
        lookup_res = self.table.lookup(func_name)
        if self.table.get_current_nesting_level == lookup_res.nesting_level:
            return ['lw $t0, -4($sp)', 'sw $t0, -4($fp)']

        return ['sw $sp, -4($fp)']

    def exit_scope(self, func):
        framelength = self.table.lookup(func).entity.frame_length
        return ['add $sp, $sp -%s' % framelength]

    def setup_parameters(self, quads):
        ret = []

        i = 0
        for quad in quads:
            qid = ['L_%s:' % quad.id]
            ret += qid

            if quad.term1 == 'cv':
                ret += self.loadvr(quad.term0, 0)
                ret += ['sw $t0, -%s($fp)' % (12 + i * 4)]

            if quad.term1 == 'ref':
                caller_nesting_level = self.table.get_current_nesting_level()
                lookup_res_var = self.table.lookup(quad.term0)
                if caller_nesting_level == lookup_res_var.nesting_level:
                    if isinstance(lookup_res_var.entity, ParameterEntity
                                  ) and lookup_res_var.entity.mode == 'ref':
                        ret += [
                            'lw $t0, -%s($sp)' % lookup_res_var.entity.offset,
                            'sw $t0, -%s($fp)' % (12 + 4 * i)
                        ]
                    else:
                        ret += [
                            'add $t0, $sp, -%s' % lookup_res_var.entity.offset,
                            'sw $t0, -%s($fp)' % (12 + 4 * i)
                        ]
                else:
                    ret += self.gnlvcode(quad.term0)

                    if isinstance(lookup_res_var.entity, ParameterEntity
                                  ) and lookup_res_var.entity.mode == 'ref':
                        ret += [
                            'lw $t0, ($t0)',
                            'sw $t0, -%s($fp)' % (12 + 4 * i)
                        ]
                    else:
                        ret += ['sw $t0, -%s($fp)' % (12 + 4 * i)]

            if quad.term1 == 'ret':
                lookup_res = self.table.lookup(quad.term0)
                ret += [
                    'add $t0, $sp, -%s' % lookup_res.entity.offset,
                    'sw $t0, -8($fp)'
                ]

            i += 1

        return ret

    def translate_quad(self, quad):
        qid = ['L_%s:' % quad.id]

        if quad.op == 'begin_block':
            return qid + ['%s:' % quad.term0] + self.new_scope_setup()

        if quad.op == ':=':
            return qid + self.loadvr(quad.term0, 1) + self.storerv(
                1, quad.target)

        if quad.op == 'int' or quad.op == 'par':
            return qid + []

        if quad.op == '+':
            return qid + self.loadvr(quad.term0, 1) + self.loadvr(
                quad.term1, 2) + ['add $t1, $t1, $t2'] + self.storerv(
                    1, quad.target)

        if quad.op == '-':
            return qid + self.loadvr(quad.term0, 1) + self.loadvr(
                quad.term1, 2) + ['sub $t1, $t1, $t2'] + self.storerv(
                    1, quad.target)

        if quad.op == '*':
            return qid + self.loadvr(quad.term0, 1) + self.loadvr(
                quad.term1, 2) + ['mul $t1, $t1, $t2'] + self.storerv(
                    1, quad.target)

        if quad.op == '/':
            return qid + self.loadvr(quad.term0, 1) + self.loadvr(
                quad.term1, 2) + ['div $t1, $t1, $t2'] + self.storerv(
                    1, quad.target)

        if quad.op == 'jump':
            return qid + ['j L_%s' % quad.target]

        if quad.op == '=':
            return qid + self.loadvr(quad.term0, 1) + self.loadvr(
                quad.term1, 2) + ['beq $t1, $t2, L_%s' % quad.target]

        if quad.op == '<>':
            return qid + self.loadvr(quad.term0, 1) + self.loadvr(
                quad.term1, 2) + ['bne $t1, $t2, L_%s' % quad.target]

        if quad.op == '>':
            return qid + self.loadvr(quad.term0, 1) + self.loadvr(
                quad.term1, 2) + ['bgt $t1, $t2, L_%s' % quad.target]

        if quad.op == '<':
            return qid + self.loadvr(quad.term0, 1) + self.loadvr(
                quad.term1, 2) + ['blt $t1, $t2, L_%s' % quad.target]

        if quad.op == '>=':
            return qid + self.loadvr(quad.term0, 1) + self.loadvr(
                quad.term1, 2) + ['bge $t1, $t2, L_%s' % quad.target]

        if quad.op == '<=':
            return qid + self.loadvr(quad.term0, 1) + self.loadvr(
                quad.term1, 2) + ['ble $t1, $t2, L_%s' % quad.target]

        if quad.op == 'retv':
            return qid + self.loadvr(quad.term0, 1) + [
                'lw $t0, -8($sp)', 'sw $t1, ($t0)'
            ] + self.jump_to_ra()

        if quad.op == 'call':
            return self.init_call(quad.term0) + qid + ['jal %s' % quad.term0
                                                       ] + self.exit_scope(
                                                           quad.term0)

        if quad.op == 'end_block':
            return qid + []

        if quad.op == 'out':
            return qid + self.loadvr(quad.term0, 1) + [
                'li $v0, 1', 'move $a0, $t1', 'syscall', 'li $a0, 0xA',
                'li $v0, 0XB', 'syscall'
            ]

        if quad.op == 'inp':
            return qid + ['li $v0, 5', 'syscall', 'move $t3, $v0'
                          ] + self.storerv(3, quad.term0)

        raise Exception('Unsupported quad type to translate: %s' % str(quad))

    def formatted(self):
        return '\n'.join('\t%s' % line if not line.endswith(':') else line
                         for line in self.generated)


class SyntaxAnal:
    def __init__(self, tokens):
        self.tokens = tokens
        self.exits = []
        self.table = SymbolTable()
        self.quad_gen = QuadGenerator(table=self.table)
        self.last_pos = None
        self.returns_of_scopes = []
        self.inside_repeat = 0
        self.final = FinalGen(self.table, self.quad_gen)

    def ensure_we_do_not_redeclare(self, name):
        if self.table.lookup_on_current_scope(name) is not None:
            raise CompilationError(
                pos=self.last_pos, msg='Redeclaring %s is not allowed.' % name)

    def check_syntax(self):
        self.parse_program()
        if len(self.tokens) > 0:
            raise Exception('Unexpected token after endprogram.')

    def peek_type(self):
        return self.tokens[0].type

    def consume(self, type):
        if self.peek(type):
            tk = self.tokens.pop(0)
            self.last_pos = tk.pos
            return tk
        else:
            raise SyntaxAnalyzerError(
                pos=self.tokens[0].pos,
                expected_type=type,
                got_token=self.tokens[0])

    def peek(self, type):
        if len(self.tokens) == 0:
            raise Exception('Unexpected EOF. Maybe endprogram is missing.')
        return self.peek_type() == type

    def parse_program(self):
        self.consume('program')
        name = self.consume('id').value
        self.final.generate_jump_to_main()
        self.quad_gen.genquad('begin_block', name, '_', '_')
        self.parse_block()
        self.final.generate_program_exit(self.quad_gen.nextquad())
        self.quad_gen.genquad('halt', '_', '_', '_')
        self.quad_gen.genquad('end_block', name, '_', '_')
        self.consume('endprogram')

    def parse_block(self):
        self.table.create_scope()
        self.parse_declarations()
        self.parse_subprograms()
        self.parse_statements()

        self.table.fill_in_framelength_on_callee()
        self.final.generate_block()
        self.table.destroy_scope()

    def parse_declarations(self):
        if self.peek('declare'):
            self.consume('declare')
            self.parse_varlist()
            self.consume('enddeclare')

    def parse_varlist(self):
        if self.peek('id'):
            vid = self.consume('id').value
            self.ensure_we_do_not_redeclare(vid)
            self.quad_gen.genquad('int', vid, '_', '_')
            self.table.add_entity(VariableEntity(vid))

            while self.peek('comma'):
                self.consume('comma')
                vid = self.consume('id').value
                self.ensure_we_do_not_redeclare(vid)
                self.quad_gen.genquad('int', vid, '_', '_')
                self.table.add_entity(VariableEntity(vid))

    def parse_subprograms(self):
        while self.peek('procedure') or self.peek('function'):
            self.parse_procorfunc()

    def parse_procorfunc(self):
        if self.peek('procedure'):
            self.consume('procedure')
            name = self.consume('id').value
            self.ensure_we_do_not_redeclare(name)
            self.table.add_entity(
                FunctionEntity(
                    name, self.quad_gen.nextquad(), type='procedure'))
            self.quad_gen.genquad('begin_block', name, '_', '_')
            self.parse_procorfuncbody()
            self.quad_gen.genquad('end_block', name, '_', '_')
            self.consume('endprocedure')
        else:
            self.consume('function')
            name = self.consume('id').value
            self.ensure_we_do_not_redeclare(name)
            self.table.add_entity(
                FunctionEntity(name, self.quad_gen.nextquad()))
            self.returns_of_scopes.append([])
            self.quad_gen.genquad('begin_block', name, '_', '_')
            self.parse_procorfuncbody()
            self.quad_gen.genquad('end_block', name, '_', '_')
            self.consume('endfunction')

            our_returns = self.returns_of_scopes.pop()
            if len(our_returns) < 1:
                raise CompilationError(
                    pos=self.last_pos,
                    msg='End of function block and no return found.',
                    suggestion='Did you forget to return?')

    def parse_procorfuncbody(self):
        self.parse_formalpars()
        self.parse_block()

    def parse_formalpars(self):
        self.consume('oparen')
        self.parse_formalparlist()
        self.consume('cparen')

    def parse_formalparlist(self):
        if self.peek('in') or self.peek('inout'):
            self.parse_formalparitem()

            while self.peek('comma'):
                self.consume('comma')
                self.parse_formalparitem()

    def parse_formalparitem(self):
        mode = None
        if self.peek('in'):
            self.consume('in')
            mode = 'cv'
        else:
            self.consume('inout')
            mode = 'ref'

        name = self.consume('id').value
        self.table.add_argument(Argument(name, mode))

    def parse_statements(self):
        self.parse_statement()

        while self.peek('semicolon'):
            self.consume('semicolon')
            self.parse_statement()

    def parse_statement(self):
        if self.peek('id'):
            self.parse_assignmentstat()
        elif self.peek('if'):
            self.parse_ifstat()
        elif self.peek('while'):
            self.parse_whilestat()
        elif self.peek('repeat'):
            self.parse_repeatstat()
        elif self.peek('exit'):
            self.parse_exitstat()
        elif self.peek('switch'):
            self.parse_switchstat()
        elif self.peek('forcase'):
            self.parse_forcasestat()
        elif self.peek('call'):
            self.parse_callstat()
        elif self.peek('return'):
            self.parse_returnstat()
        elif self.peek('input'):
            self.parse_inputstat()
        elif self.peek('print'):
            self.parse_printstat()

    def parse_assignmentstat(self):
        target = self.consume('id').value
        op = self.consume('assign').value
        value = self.parse_expression()
        self.quad_gen.genquad(op, value, '_', target)

    def parse_ifstat(self):
        self.consume('if')
        cond = self.parse_condition()
        self.consume('then')
        self.quad_gen.backpatch(cond.true, self.quad_gen.nextquad())
        self.parse_statements()
        after_if_jump = self.quad_gen.nextquad()
        self.quad_gen.genquad('jump', '_', '_', '_')

        self.quad_gen.backpatch(cond.false, self.quad_gen.nextquad())
        self.parse_elsepart()
        self.consume('endif')
        self.quad_gen.backpatch([after_if_jump], self.quad_gen.nextquad())

    def parse_elsepart(self):
        if self.peek('else'):
            self.consume('else')
            self.parse_statements()

    def parse_repeatstat(self):
        self.consume('repeat')
        in_repeat = self.quad_gen.nextquad()

        self.inside_repeat += 1

        old_exits = self.exits
        self.exits = []
        self.parse_statements()
        self.quad_gen.genquad('jump', '_', '_', in_repeat)

        self.quad_gen.backpatch(self.exits, self.quad_gen.nextquad())
        self.exits = old_exits

        self.consume('endrepeat')
        self.inside_repeat -= 1

    def parse_exitstat(self):
        self.consume('exit')
        if self.inside_repeat < 1:
            raise CompilationError(
                pos=self.last_pos,
                msg='Found exit outside a repeat block.',
                suggestion='Remove the exit?')
        self.exits.append(self.quad_gen.nextquad())
        self.quad_gen.genquad('jump', '_', '_', '_')

    def parse_whilestat(self):
        self.consume('while')
        pre_cond = self.quad_gen.nextquad()
        cond = self.parse_condition()
        in_while = self.quad_gen.nextquad()
        self.quad_gen.backpatch(cond.true, in_while)
        self.parse_statements()
        self.quad_gen.genquad('jump', '_', '_', pre_cond)

        after_while = self.quad_gen.nextquad()
        self.quad_gen.backpatch(cond.false, after_while)
        self.consume('endwhile')

    def parse_switchstat(self):
        self.consume('switch')
        expr = self.parse_expression()

        jumps_when_done = self.parse_case(expr)
        while self.peek('case'):
            jumps_when_done += self.parse_case(expr)

        self.consume('endswitch')
        self.quad_gen.backpatch(jumps_when_done, self.quad_gen.nextquad())

    def parse_case(self, expr1):
        self.consume('case')
        expr2 = self.parse_expression()

        neq_quad = self.quad_gen.nextquad()
        self.quad_gen.genquad('<>', expr1, expr2, '_')

        self.consume('colon')
        self.parse_statements()
        jump_when_done = self.quad_gen.nextquad()
        self.quad_gen.genquad('jump', '_', '_', '_')
        self.quad_gen.backpatch([neq_quad], self.quad_gen.nextquad())
        return [jump_when_done]

    def parse_forcasestat(self):
        self.consume('forcase')
        in_forcase = self.quad_gen.nextquad()
        was_any_true_flag = self.quad_gen.newtemp()
        self.quad_gen.genquad(':=', '0', '_', was_any_true_flag)

        self.parse_when(was_any_true_flag)

        while self.peek('when'):
            self.parse_when(was_any_true_flag)

        self.quad_gen.genquad('=', '1', was_any_true_flag, in_forcase)
        self.consume('endforcase')

    def parse_when(self, was_any_true_flag):
        self.consume('when')
        cond = self.parse_condition()

        self.consume('colon')

        when_ok = self.quad_gen.nextquad()
        self.quad_gen.backpatch(cond.true, when_ok)
        self.quad_gen.genquad(':=', '1', '_', was_any_true_flag)
        self.parse_statements()

        next_when = self.quad_gen.nextquad()
        self.quad_gen.backpatch(cond.false, next_when)

    def parse_callstat(self):
        self.consume('call')
        name = self.consume('id').value
        self.ensure_a_valid_procedure(name)
        par_types = self.parse_actualpars()
        self.ensure_signature(name, par_types)
        self.quad_gen.genquad('call', name, '_', '_')

    def ensure_a_valid_procedure(self, name):
        if not self.table.has_a_procedure(name):
            self.error_incorrect_use(name, 'procedure')

    def ensure_signature(self, name, types):
        if not self.table.has_a_callable_with_signature(name, types):
            raise CompilationError(
                pos=self.last_pos, msg='Invalid signature for "%s".' % name)

    def parse_returnstat(self):
        self.consume('return')
        exp = self.parse_expression()
        self.quad_gen.genquad('retv', exp, '_', '_')

        if not self.table.am_i_inside_function():
            raise CompilationError(
                pos=self.last_pos,
                msg='Found stray return outside function block.',
                suggestion='Remove the stray return.')
        self.returns_of_scopes[-1].append('return')

    def parse_printstat(self):
        self.consume('print')
        expr = self.parse_expression()
        self.quad_gen.genquad('out', expr, '_', '_')

    def parse_inputstat(self):
        self.consume('input')
        name = self.consume('id').value
        self.quad_gen.genquad('inp', name, '_', '_')

    def parse_actualpars(self):
        self.consume('oparen')
        pars = self.parse_actualparlist()
        self.consume('cparen')
        return pars

    def parse_actualparlist(self):
        pars = []
        if self.peek('in') or self.peek('inout'):
            pars.append(self.parse_actualparitem())

            while self.peek('comma'):
                self.consume('comma')
                pars.append(self.parse_actualparitem())
        return pars

    def parse_actualparitem(self):
        if self.peek('in'):
            self.consume('in')
            par = self.parse_expression()
            self.quad_gen.genquad('par', par, 'cv', '_')
            return 'cv'
        else:
            self.consume('inout')
            par = self.consume('id').value
            self.quad_gen.genquad('par', par, 'ref', '_')
            return 'ref'

    def parse_condition(self):
        b = TrueFalse()
        q1 = self.parse_boolterm()
        b.true = q1.true
        b.false = q1.false

        while self.peek('or'):
            self.consume('or')
            self.quad_gen.backpatch(b.false, self.quad_gen.nextquad())

            q2 = self.parse_boolterm()
            b.true += q2.true
            b.false = q2.false

        return b

    def parse_boolterm(self):
        q = TrueFalse()
        r1 = self.parse_boolfactor()

        q.true = r1.true
        q.false = r1.false

        while self.peek('and'):
            self.consume('and')
            self.quad_gen.backpatch(q.true, self.quad_gen.nextquad())

            r2 = self.parse_boolfactor()
            q.false += r2.false
            q.true = r2.true

        return q

    def parse_boolfactor(self):
        if self.peek('not'):
            self.consume('not')
            self.consume('obracket')
            cond = self.parse_condition()
            self.consume('cbracket')
            return TrueFalse(true=cond.false, false=cond.true)
        elif self.peek('obracket'):
            self.consume('obracket')
            cond = self.parse_condition()
            self.consume('cbracket')
            return cond
        elif self.peek('true'):
            self.consume('true')
            qid = self.quad_gen.nextquad()
            self.quad_gen.genquad('jump', '_', '_', '_')
            return TrueFalse(true=[qid])
        elif self.peek('false'):
            self.consume('false')
            qid = self.quad_gen.nextquad()
            self.quad_gen.genquad('jump', '_', '_', '_')
            return TrueFalse(false=[qid])
        else:
            exp1 = self.parse_expression()
            relop = self.parse_relationaloper()
            exp2 = self.parse_expression()

            relop_qid = self.quad_gen.nextquad()
            self.quad_gen.genquad(relop, exp1, exp2, '_')

            nop_qid = self.quad_gen.nextquad()
            self.quad_gen.genquad('jump', '_', '_', '_')
            return TrueFalse(true=[relop_qid], false=[nop_qid])

    def parse_expression(self):
        sign = self.parse_optionalsign()
        term = self.parse_term()

        while self.peek('plus') or self.peek('minus'):
            op = self.parse_addoper()
            secterm = self.parse_term()
            target = self.quad_gen.newtemp()
            self.quad_gen.genquad(op, term, secterm, target)
            term = target

        signed_term = term
        if sign == '-':
            signed_term = self.quad_gen.newtemp()
            self.quad_gen.genquad('*', term, '-1', signed_term)

        return signed_term

    def parse_term(self):
        factor = self.parse_factor()

        while self.peek('mul') or self.peek('div'):
            op = self.parse_muloper()
            secfactor = self.parse_factor()
            target = self.quad_gen.newtemp()
            self.quad_gen.genquad(op, factor, secfactor, target)
            factor = target

        return factor

    def error_incorrect_use(self, name, as_type):
        raise CompilationError(
            pos=self.last_pos,
            msg='Using "%s" as a %s but it\'s not one.' % (name, as_type))

    def parse_factor(self):
        if self.peek('oparen'):
            self.consume('oparen')
            exp = self.parse_expression()
            self.consume('cparen')
            return exp

        elif self.peek('id'):
            vid = self.consume('id').value
            place_of_fn_call = self.parse_idtail(vid)
            if place_of_fn_call is not None:
                self.quad_gen.genquad('call', vid, '_', '_')
                return place_of_fn_call
            else:
                self.ensure_a_valid_variable(vid)
                return vid

        else:
            return self.consume('int').value

    def ensure_a_valid_function(self, name):
        if not self.table.has_a_function(name):
            self.error_incorrect_use(name, 'function')

    def ensure_a_valid_variable(self, name):
        if not self.table.has_a_variable(name):
            self.error_incorrect_use(name, 'variable')

    def parse_idtail(self, fn_name):
        if self.peek('oparen'):
            par_types = self.parse_actualpars()
            self.ensure_a_valid_function(fn_name)
            self.ensure_signature(fn_name, par_types)
            retval = self.quad_gen.newtemp(False)
            self.quad_gen.genquad('par', retval, 'ret', '_')
            self.table.add_entity(ParameterEntity(retval, 'ret'))
            return retval

        return None

    def parse_relationaloper(self):
        if self.peek('eq'):
            return self.consume('eq').value
        elif self.peek('le'):
            return self.consume('le').value
        elif self.peek('ge'):
            return self.consume('ge').value
        elif self.peek('lt'):
            return self.consume('lt').value
        elif self.peek('gt'):
            return self.consume('gt').value
        else:
            return self.consume('neq').value

    def parse_addoper(self):
        if self.peek('plus'):
            return self.consume('plus').value
        else:
            return self.consume('minus').value

    def parse_muloper(self):
        if self.peek('mul'):
            return self.consume('mul').value
        else:
            return self.consume('div').value

    def parse_optionalsign(self):
        if self.peek('plus') or self.peek('minus'):
            return self.parse_addoper()

        return ''


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_file')
    args = parser.parse_args()

    basename = os.path.basename(args.source_file)
    sourcename = basename.split('.')[0]
    intermediate_filename = '%s.eeli' % sourcename
    final_filename = '%s.s' % sourcename

    with open(args.source_file, 'r') as source_file:
        source = source_file.read()
    try:
        tokens = Lexer(source).tokenize()
        syntax_anal = SyntaxAnal(tokens)
        syntax_anal.check_syntax()
        print('Putting intermediate code in [%s]...' % intermediate_filename)
        with open(intermediate_filename, 'w') as intermediate_file:
            intermediate_file.write(str(syntax_anal.quad_gen))
        print('Putting final code in [%s]...' % final_filename)
        with open(final_filename, 'w') as s_file:
            s_file.write(syntax_anal.final.formatted())
    except CompilationError as e:
        print('%s:%s\n' % (args.source_file, str(e)))
        sys.exit(1)
