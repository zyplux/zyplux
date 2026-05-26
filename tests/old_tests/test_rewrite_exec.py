"""rewrite_exec_line — the idempotent .desktop Exec= rewrite (env prefix, --switches, --enable-features, field-code placement); pure string surgery worth pinning directly."""

from functools import partial

from totchef.cooks.desktop_cook import rewrite_exec_line


def test_inserts_env_switches_and_features_before_field_code():
    result = rewrite_exec_line(
        "/usr/bin/brave-browser %U",
        env={"LIBVA_DRIVER_NAME": "nvidia"},
        features=["VaapiOnNvidiaGPUs", "WaylandLinuxDrmSyncobj"],
        switches=["enable-zero-copy"],
    )
    assert result == ("env LIBVA_DRIVER_NAME=nvidia /usr/bin/brave-browser --enable-zero-copy --enable-features=VaapiOnNvidiaGPUs,WaylandLinuxDrmSyncobj %U")


def test_is_idempotent_when_reapplied():
    apply = partial(
        rewrite_exec_line,
        env={"LIBVA_DRIVER_NAME": "nvidia"},
        features=["VaapiOnNvidiaGPUs"],
        switches=["enable-zero-copy"],
    )
    once = apply("/usr/bin/app %U")
    twice = apply(once)
    assert once == twice


def test_dedupes_key_value_switch_replacing_the_old_value():
    result = rewrite_exec_line(
        "/bin/app --render-node-override=/old %F",
        env={},
        features=[],
        switches=["render-node-override=/dev/dri/renderD129"],
    )
    assert result == "/bin/app --render-node-override=/dev/dri/renderD129 %F"


def test_appends_at_end_when_there_is_no_field_code():
    result = rewrite_exec_line("/bin/app", env={}, features=["Feat"], switches=["sw"])
    assert result == "/bin/app --sw --enable-features=Feat"


def test_strips_a_prior_env_prefix_instead_of_nesting_it():
    result = rewrite_exec_line("env OLD=1 /bin/app %u", env={"NEW": "2"}, features=[], switches=[])
    assert result == "env NEW=2 /bin/app %u"
