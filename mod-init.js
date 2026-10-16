/*
 * DOCTRINE mod entry point.
 * Ships as multiplay/script/mods/init.js — the engine's designated mod hook,
 * overriding the empty vanilla stub. Included LAST by rules/includes.js, so
 * doctrine.js can capture and chain every vanilla event handler.
 */
include("multiplay/script/mods/doctrine.js");
