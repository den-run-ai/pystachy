import sys
names = """Name Int Float Complex String FStringStart FStringMiddle FStringEnd TStringStart TStringMiddle TStringEnd IpyEscapeCommand Comment Newline NonLogicalNewline Indent Dedent EndOfFile Question Exclamation Lpar Rpar Lsqb Rsqb Colon Comma Semi Plus Minus Star Slash Vbar Amper Less Greater Equal Dot Percent Lbrace Rbrace EqEqual NotEqual LessEqual GreaterEqual Tilde CircumFlex LeftShift RightShift DoubleStar DoubleStarEqual PlusEqual MinusEqual StarEqual SlashEqual PercentEqual AmperEqual VbarEqual CircumflexEqual LeftShiftEqual RightShiftEqual DoubleSlash DoubleSlashEqual ColonEqual At AtEqual Rarrow Ellipsis And As Assert Async Await Break Class Continue Def Del Elif Else Except False Finally For From Global If Import In Is Lambda None Nonlocal Not Or Pass Raise Return True Try While With Yield Case Lazy Match Type Unknown""".split()
display = {
 'Unknown':'Unknown','Newline':'newline','NonLogicalNewline':'NonLogicalNewline','Indent':'indent','Dedent':'dedent','EndOfFile':'end of file',
 'Name':'name','Int':'int','Float':'float','Complex':'complex','String':'string','FStringStart':'FStringStart','FStringMiddle':'FStringMiddle',
 'FStringEnd':'FStringEnd','TStringStart':'TStringStart','TStringMiddle':'TStringMiddle','TStringEnd':'TStringEnd','IpyEscapeCommand':'IPython escape command',
 'Comment':'comment','Question':'`?`','Exclamation':'`!`','Lpar':'`(`','Rpar':'`)`','Lsqb':'`[`','Rsqb':'`]`','Lbrace':'`{`','Rbrace':'`}`','Equal':'`=`',
 'ColonEqual':'`:=`','Dot':'`.`','Colon':'`:`','Semi':'`;`','Comma':'`,`','Rarrow':'`->`','Plus':'`+`','Minus':'`-`','Star':'`*`','DoubleStar':'`**`',
 'Slash':'`/`','DoubleSlash':'`//`','Percent':'`%`','Vbar':'`|`','Amper':'`&`','CircumFlex':'`^`','LeftShift':'`<<`','RightShift':'`>>`','Tilde':'`~`',
 'At':'`@`','Less':'`<`','Greater':'`>`','EqEqual':'`==`','NotEqual':'`!=`','LessEqual':'`<=`','GreaterEqual':'`>=`','PlusEqual':'`+=`','MinusEqual':'`-=`',
 'StarEqual':'`*=`','DoubleStarEqual':'`**=`','SlashEqual':'`/=`','DoubleSlashEqual':'`//=`','PercentEqual':'`%=`','VbarEqual':'`|=`','AmperEqual':'`&=`',
 'CircumflexEqual':'`^=`','LeftShiftEqual':'`<<=`','RightShiftEqual':'`>>=`','AtEqual':'`@=`','Ellipsis':'`...`'}
kw = "False None True And As Assert Async Await Break Class Continue Def Del Elif Else Except Finally For From Global If Import In Is Lambda Nonlocal Not Or Pass Raise Return Try While With Yield Case Lazy Match Type".split()
for k in kw:
    display.setdefault(k, '`' + (k if k in ('False','None','True') else k.lower()) + '`')
out = []
out.append('"""Token kinds and flags of the lexer: the order of ruff_python_ast\'s TokenKind (see THIRD_PARTY_NOTICES)."""\n')
for i, n in enumerate(names):
    out.append(f"T_{n.upper()} = {i}\n")
out.append(f"N_KINDS = {len(names)}\n\n")
out.append("# TokenKind's Display, for error messages\n")
out.append("KIND_TEXT: list[str] = [\n")
for n in names:
    out.append(f"    {display[n]!r},\n")
out.append("]\n")
open(sys.argv[1], 'w').write(''.join(out))
print(len(names))
