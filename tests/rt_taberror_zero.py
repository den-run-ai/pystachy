# TabError (a SyntaxError) with a false message, 0: "<no detail available>" (msg or "...")
import sys

raise TabError(len(sys.argv) - 3) from None
