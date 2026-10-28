"""What proki can do, as tools: the same ones for the app and for an AI agent.

    reference                           what a program can use, its values now, and the programs that run
    evaluate                            an expression's value now, and its type
    playground                          made-up signals and variables, to try an expression or an action on
    get_program                         one program, state by state, and what it depends on
    program_specs                       one program's specs, or the global scope's, as they're edited
    list_specs                          the specs of a kind, as they're written
    add_<kind>                          a new input, variable, signal, rule, program, state, branch or action
    update_<kind>                       one, found by its fields, with `changes`
    remove_<kind>                       one, and what it owns
    apply_changes                       several changes, all of them kept or none
    switch_program                      a program on or off
    set_value                           a variable's value, set now
    reset_program                       a program, or the global scope, back to its default

    get_media                           the pictures and sounds, a page at a time or by keys
    add_media, remove_media             a file or a folder of yours in (a copy), or some deleted (gone in a week)
    rename_media                        one's name, what you see (its key stays)
    list_pools, set_pool                what a popup draws from where no action says ("questions")
    get_picks, set_picks                what a poke or a question draws from, by its action's id

    read_records                        a kind of record's (work.groups, work.tasks), in your order
    {add,change,remove,move}_record     a record: a new one, some of its fields, deleted, or put before another
    read_ops                            the changes suggested to the groups' tasks
    {add,change,remove}_op              a change suggested: a new one, some of its fields, or taken away

    get_settings, set_settings          the LLM and jev: each one's provider, key and model, asked from then on
    test_connection, list_models        whether one answers at a provider, and the models there

    suggest, send_suggestions           a suggestion for proki's developer, kept until you're online

A poke's or a question's pictures and sounds are chosen in the media library, by its action's
id, not in its program.

A mistake is the tool's error, saying where it is, so who called it can fix that one place.
"""
