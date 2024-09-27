use std::{env, fs, path::PathBuf, process::Command};

use clap::Parser;

#[derive(Parser)]
#[command(version, about)]
/// Generate licenses for cosmic packages
struct Cli {
    /// Working directory
    workdir: PathBuf,
    /// Clean working directory
    #[arg(short, long)]
    clean: bool,
}

const PACKAGES: [&str; 22] = [
    "cosmic-applibrary",
    "cosmic-applets",
    "cosmic-bg",
    "cosmic-comp",
    "cosmic-edit",
    "cosmic-files",
    "cosmic-greeter",
    "cosmic-icons",
    "cosmic-launcher",
    "cosmic-notifications",
    "cosmic-osd",
    "cosmic-panel",
    "cosmic-randr",
    "cosmic-screenshot",
    "cosmic-session",
    "cosmic-settings",
    "cosmic-settings-daemon",
    "cosmic-store",
    "cosmic-term",
    "cosmic-workspaces-epoch",
    "launcher",
    "xdg-desktop-portal-cosmic",
];

fn main() -> anyhow::Result<()> {
    let args = Cli::parse();
    let base_working_dir = args.workdir.canonicalize().unwrap();
    if args.clean {
        let _ = fs::remove_dir_all(&base_working_dir);
        let _ = fs::create_dir(&base_working_dir);
    }
    println!("Working directory: {:?}", &base_working_dir);
    let mut result_string = "".to_string();
    let res = || -> anyhow::Result<()> {
        for package in PACKAGES {
            println!("Package: {}", package);
            let _ = Command::new("git")
                .current_dir(&base_working_dir)
                .arg("clone")
                .arg(format!("https://github.com/pop-os/{}.git", package))
                .status()?;
            let output = Command::new("sh")
                .current_dir(base_working_dir.join(package))
                .arg("-c")
                .arg(
                    r##"cargo tree --workspace --edges no-build,no-dev,no-proc-macro --no-dedupe --target all --prefix none --format "{l}" | sort | uniq | sed '/OR/ s/.*/(&)/' | awk '{printf("%s AND ", $0)} END {print ""}' | sed 's/AND$//'"##
                ).output()?;

            let (stdout, stderr) = (
                String::from_utf8(output.stdout).unwrap(),
                String::from_utf8(output.stderr).unwrap(),
            );
            println!("stdout: {} stderr: {}\n", &stdout, &stderr);
            result_string.push_str(&format!("{}\n{}\n\n", package, &stdout));
        }
        Ok(())
    }();

    if res.is_err() {
        eprintln!("There was a problem with the program. Saving what was grabbed.")
    } else {
        println!("Program executed successfully!");
    }
    let _ = env::set_current_dir(&base_working_dir);
    fs::write(
        &base_working_dir.join("cosmic_licenses.txt"),
        &result_string,
    )?;
    Ok(())
}
