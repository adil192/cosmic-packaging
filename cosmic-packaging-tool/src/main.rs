use std::{
    collections::HashSet,
    env,
    fs::{self, File},
    io::{self, BufRead, Write},
    path::{Path, PathBuf},
    process::Command,
};

use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(version, about)]
/// Tools for fedora cosmic packaging
struct Cli {
    /// Command to run
    #[command(subcommand)]
    action: Commands,
}

#[derive(Subcommand, Clone, Debug)]
enum Commands {
    /// Update the licenses for the cosmic packages
    UpdateLicenses {
        /// Working directory
        workdir: PathBuf,
        /// Clean working directory
        #[arg(short, long)]
        clean: bool,
        /// Packaging directory to rewrite cosmic spec files (OPTIONAL)
        #[arg(long)]
        packaging_dir: Option<PathBuf>,
        /// Optionally exclude GPL-3.0 from the license summary. cosmic-protocols has had its
        /// license clarified but is still on old versions for all the packages.
        #[arg(long)]
        exclude_gpl_3: bool,
    },
    AutobumpReleases {
        /// Packaging directory to rewrite cosmic spec files
        packaging_dir: PathBuf,
        /// Release to set (i.e. '%autorelease')
        release: String,
    },
}

const PACKAGES_ITER: [Packages; 22] = [
    Packages::CosmicAppLibrary,
    Packages::CosmicApplets,
    Packages::CosmicBg,
    Packages::CosmicComp,
    Packages::CosmicEdit,
    Packages::CosmicFiles,
    Packages::CosmicGreeter,
    Packages::CosmicIcons,
    Packages::CosmicLauncher,
    Packages::CosmicNotifications,
    Packages::CosmicOsd,
    Packages::CosmicPanel,
    Packages::CosmicRandr,
    Packages::CosmicScreenshot,
    Packages::CosmicSession,
    Packages::CosmicSettings,
    Packages::CosmicSettingsDaemon,
    Packages::CosmicStore,
    Packages::CosmicTerm,
    Packages::CosmicWorkspaces,
    Packages::PopLauncher,
    Packages::XdgDesktopPortalCosmic,
];

enum Packages {
    CosmicAppLibrary,
    CosmicApplets,
    CosmicBg,
    CosmicComp,
    CosmicEdit,
    CosmicFiles,
    CosmicGreeter,
    CosmicIcons,
    CosmicLauncher,
    CosmicNotifications,
    CosmicOsd,
    CosmicPanel,
    CosmicRandr,
    CosmicScreenshot,
    CosmicSession,
    CosmicSettings,
    CosmicSettingsDaemon,
    CosmicStore,
    CosmicTerm,
    CosmicWorkspaces,
    PopLauncher,
    XdgDesktopPortalCosmic,
}

impl Packages {
    fn to_repo<'a>(&self) -> &'a str {
        match self {
            Packages::CosmicAppLibrary => "cosmic-applibrary",
            Packages::CosmicApplets => "cosmic-applets",
            Packages::CosmicBg => "cosmic-bg",
            Packages::CosmicComp => "cosmic-comp",
            Packages::CosmicEdit => "cosmic-edit",
            Packages::CosmicFiles => "cosmic-files",
            Packages::CosmicGreeter => "cosmic-greeter",
            Packages::CosmicIcons => "cosmic-icons",
            Packages::CosmicLauncher => "cosmic-launcher",
            Packages::CosmicNotifications => "cosmic-notifications",
            Packages::CosmicOsd => "cosmic-osd",
            Packages::CosmicPanel => "cosmic-panel",
            Packages::CosmicRandr => "cosmic-randr",
            Packages::CosmicScreenshot => "cosmic-screenshot",
            Packages::CosmicSession => "cosmic-session",
            Packages::CosmicSettings => "cosmic-settings",
            Packages::CosmicSettingsDaemon => "cosmic-settings-daemon",
            Packages::CosmicStore => "cosmic-store",
            Packages::CosmicTerm => "cosmic-term",
            Packages::CosmicWorkspaces => "cosmic-workspaces-epoch",
            Packages::PopLauncher => "launcher",
            Packages::XdgDesktopPortalCosmic => "xdg-desktop-portal-cosmic",
        }
    }

    fn package_name<'a>(&self) -> &'a str {
        match self {
            Packages::CosmicAppLibrary => "cosmic-app-library",
            Packages::CosmicApplets => "cosmic-applets",
            Packages::CosmicBg => "cosmic-bg",
            Packages::CosmicComp => "cosmic-comp",
            Packages::CosmicEdit => "cosmic-edit",
            Packages::CosmicFiles => "cosmic-files",
            Packages::CosmicGreeter => "cosmic-greeter",
            Packages::CosmicIcons => "cosmic-icon-theme",
            Packages::CosmicLauncher => "cosmic-launcher",
            Packages::CosmicNotifications => "cosmic-notifications",
            Packages::CosmicOsd => "cosmic-osd",
            Packages::CosmicPanel => "cosmic-panel",
            Packages::CosmicRandr => "cosmic-randr",
            Packages::CosmicScreenshot => "cosmic-screenshot",
            Packages::CosmicSession => "cosmic-session",
            Packages::CosmicSettings => "cosmic-settings",
            Packages::CosmicSettingsDaemon => "cosmic-settings-daemon",
            Packages::CosmicStore => "cosmic-store",
            Packages::CosmicTerm => "cosmic-term",
            Packages::CosmicWorkspaces => "cosmic-workspaces",
            Packages::PopLauncher => "pop-launcher",
            Packages::XdgDesktopPortalCosmic => "xdg-desktop-portal-cosmic",
        }
    }

    fn package_dir<'a>(&self, packaging_dir: &Path) -> PathBuf {
        packaging_dir.join(&format!(
            "rpms/{}/{}.spec",
            self.package_name(),
            self.package_name()
        ))
    }
}

fn main() -> anyhow::Result<()> {
    let args = Cli::parse();
    match args.action {
        Commands::UpdateLicenses {
            workdir,
            clean,
            packaging_dir,
            exclude_gpl_3,
        } => update_licenses_command(workdir, clean, packaging_dir, exclude_gpl_3),
        Commands::AutobumpReleases {
            packaging_dir,
            release,
        } => autobump_releases_command(&packaging_dir, &release),
    }
}

fn autobump_releases_command(packaging_dir: &Path, release: &str) -> anyhow::Result<()> {
    for package in PACKAGES_ITER {
        homebrew_sed(
            &package.package_dir(packaging_dir),
            "Release: ",
            &format!("Release:        {}", release),
        )?;
    }
    Ok(())
}

fn update_licenses_command(
    workdir: PathBuf,
    clean: bool,
    packaging_dir: Option<PathBuf>,
    exclude_gpl_3: bool,
) -> anyhow::Result<()> {
    let base_working_dir = workdir.canonicalize().unwrap();
    if clean {
        let _ = fs::remove_dir_all(&base_working_dir);
        let _ = fs::create_dir(&base_working_dir);
    }
    println!("Working directory: {:?}", &base_working_dir);
    let mut result_string = "".to_string();
    let res = || -> anyhow::Result<()> {
        for package in PACKAGES_ITER {
            let package_repo = package.to_repo();
            println!("Package: {}", package_repo);
            if !&base_working_dir.join(package_repo).exists() {
                let _ = Command::new("git")
                    .current_dir(&base_working_dir)
                    .arg("clone")
                    .arg(format!("https://github.com/pop-os/{}.git", package_repo))
                    .status()?;
            }
            let output = Command::new("sh")
            .current_dir(base_working_dir.join(package_repo))
            .arg("-c")
            .arg(
                r##"cargo tree --workspace --edges no-build,no-dev,no-proc-macro --no-dedupe --target all --prefix none --format "{l}" | sort | uniq"##
            ).output()?;

            let (stdout, _stderr) = (
                String::from_utf8(output.stdout).unwrap(),
                String::from_utf8(output.stderr).unwrap(),
            );
            let license_result = stdout
                .lines()
                .filter_map(|l| {
                    if l == "GPL-3.0" && exclude_gpl_3 {
                        println!("Skipping raw GPL-3.0");
                        return None;
                    }
                    let repl_or = l.replace("/", " OR ");
                    if repl_or.contains("OR") {
                        Some(format!("({})", repl_or))
                    } else {
                        Some(repl_or)
                    }
                })
                .collect::<HashSet<String>>()
                .into_iter()
                .collect::<Vec<String>>()
                .join(" AND ");
            if let Some(packaging_dir) = packaging_dir.as_deref() {
                if !license_result.is_empty() {
                    homebrew_sed(
                        &package.package_dir(packaging_dir),
                        "License: ",
                        &format!("License:        {}", &license_result),
                    )?;
                }
            }
            result_string.push_str(&format!("License:        {}", &license_result));
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

fn homebrew_sed(spec_path: &Path, search_prefix: &str, replacement: &str) -> anyhow::Result<()> {
    // Step 1: Open the file and read it line by line
    let file = File::open(spec_path)?;
    let reader = io::BufReader::new(file);

    let mut new_content = Vec::new(); // To store the modified file content

    for line in reader.lines() {
        let line = line?; // Unwrap the Result to get the actual line content
                          // Step 2: Check if the line starts with "Key:"
        if line.starts_with(search_prefix) {
            // Step 3: Replace the whole line
            new_content.push(replacement.to_string());
        } else {
            // Keep the original line
            new_content.push(line);
        }
    }

    // Step 4: Write the modified content back to the file
    let mut file = File::create(&spec_path)?; // Open the file in write mode
    for line in new_content {
        writeln!(file, "{}", line)?;
    }
    Ok(())
}
