# Sourcery Pane for Binary Ninja

Source view that syncs with disassembly when debug info and source is available.

## Description:

`Sourcery Pane` uses the magic of debug builds and having access to source code to translate the current location in disassembly into a synchronized view of source code.

The only dependency is the standard `addr2line` executable, which is what is used to do the translation between offsets and source lines.

Also features local translation paths for binaries built on other systems as well as pausing/resuming sync with disassembly.

### Background

I wrote this tool because there seems to be a lot of confusion over what is needed to go from offsets in a binary back to source.  In short, you only need three things:

1) The target binary
2) The source code the binary was built from
3) Data that translates offsets to source lines (and potentially a tool for extracting it)

Of course the first two are obvious, but the third isn't as mysterious as people think. On Linux, it is most often included in the target binary as part of the debug information when you compile with the `-g` option. For more information, you can read up on the DWARF specification [here](http://www.dwarfstd.org/doc/Debugging%20using%20DWARF.pdf).

So if you've compiled your target with `-g` (or `-gline-tables-only` with clang), you can use the binutils `addr2line` utility to query any given offset to see what source line it maps to, and that's exactly what this plugin automates.  If you're not sure if a target has the required information, you can check with a command like `readelf --debug-dump=decodedline a.out`.

### Usage

Use the dropdown `View -> Show Sourcery Pane` to pop open the sourcery pane, then drag and drop it to whatever layout works best for you.

Once you start clicking around in the disassembly, the pane will automatically update to show the source code that corresponds to the current location. Use the `Turn Source Sync On/Off` button if you want the source display to stop updating, and press it again to resume, the button text will update to indicate the current function.

If you see `No source mapping for address 0xNNNNN`, that just means that there is no mapping for the current location, which is not a problem unless you forgot to build with `-g`.

If you see a message like `[!] Source file "/home/user/code/main.cpp" not found`, that means that the original source path that the binary was built with is not available (commonly happens when you built the binary on another machine or you rm'd the source).  As long as you have EXACTLY the same files the binary was built with, you can set a translation path to point to the local location of the source files and the plugin will work perfectly.

Translation paths are a simple string substitution over the path, and you can set as many as you like.  For example, if the file `/home/tom/demo/file.c` is not found, and we have the source for the `demo` project at `/home/bob/demo/` we could fill in `tom` in the `Original Path` field and put `bob` in the `Do Path Substitution` field, or we could use the full paths: `/home/tom/demo` and `/home/bob/demo`.  Clicking the `Do Path Substitution` button sets the path in the plugin, and it will begin working once you click on the disassembly after hitting the button.

The plugin will search through all substitution paths looking for paths to files on the local machine going from longest to shortest "original path".  If you want to remove a subsitution path, fill in the original path and leave the substitution path blank, then press the `Do Path Substitution` button. The plugin will put warnings in the log if the substitution paths don't seem to be working, but it only looks to see if files exist at a given path, it doesn't do any checking to make sure the contents are correct.

IMPORTANT: Any changes to source files will result in innaccuracy of the source view, as the line information compiled into the binary reflects the exact source lines at compile-time.

## Installation Instructions

### Linux

Install the binutils package via `apt install binutils` or the equivalent with your package manager, or download an `addr2line` executable and put it in your path.

After that, just copy this folder into your plugins directory 
([instructions](https://docs.binary.ninja/guide/plugins/index.html#using-plugins)).

Only tested on Linux, probably also works on Mac.

## Minimum Version

This plugin uses `binaryninjaui` so it will probably only work on newer versions, tested on stable 1.1.1689.


