use std::{
    collections::{HashMap, HashSet},
    env,
    fs::{self, create_dir, File},
    io::{self, BufRead, Write},
    path::{Path, PathBuf},
    process::Command,
    thread,
    time::Duration,
};

use clap::{Parser, Subcommand};
use petgraph::{
    dot::{Config, Dot},
    graph::{DiGraph, NodeIndex},
};

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
    /// Autobump releases
    AutobumpReleases {
        /// Packaging directory to rewrite cosmic spec files
        packaging_dir: PathBuf,
        /// Release to set (i.e. '%autorelease')
        release: String,
    },
    /// Sets up a fedpkg build (run fkinit to start)
    SetupBuild {
        /// Working directory
        workdir: PathBuf,
        /// Package name (cosmic-comp for example)
        package_name: String,
        /// Optionally specify the branch to build
        #[arg(long)]
        build_branch: Option<String>,
        /// Srpm url (check the copr)
        #[arg(long)]
        srpm_url: Option<String>,
        /// Auto get the latest srpm from the tagged repo (beta)
        #[arg(long)]
        auto_srpm: bool,
        /// Optional source branch to get content from
        #[arg(long)]
        source_branch: Option<String>,
        /// Version (i.e. 1.0.0~alpha.6)
        #[arg(long)]
        version: Option<String>,
    },
    // /// Sets up a fedpkg build from the rawhide branch to a different branch
    // BuildForBranch {
    //     /// Working directory
    //     workdir: PathBuf,
    //     /// Package name (cosmic-comp for example)
    //     package_name: String,
    //     /// Other branch (rawhide for example)
    //     from_branch: String,
    //     /// To branch (f41 for example)
    //     to_branch: String,
    // },
    /// Build a dependency graph of the packages
    DependencyGraph { packaging_dir: PathBuf },
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

    fn spec_file<'a>(&self, packaging_dir: &Path) -> PathBuf {
        packaging_dir.join(&format!(
            "rpms/{}/{}.spec",
            self.package_name(),
            self.package_name()
        ))
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
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
        Commands::SetupBuild {
            workdir,
            package_name,
            srpm_url,
            version,
            build_branch,
            source_branch,
            auto_srpm,
        } => setup_build_command(
            &workdir,
            &package_name,
            srpm_url.as_deref(),
            version.as_deref(),
            build_branch.as_deref(),
            source_branch.as_deref(),
            auto_srpm,
        ).await,
        Commands::DependencyGraph { packaging_dir } => dependency_graph_command(&packaging_dir),
    }
}

fn dependency_graph_command(packaging_dir: &Path) -> anyhow::Result<()> {
    // Create a directed graph
    let mut graph = DiGraph::new();
    let mut nodes: HashMap<String, NodeIndex> = HashMap::new();

    for package in PACKAGES_ITER {
        if !nodes.contains_key(package.package_name()) {
            nodes.insert(
                package.package_name().to_string(),
                graph.add_node(package.package_name().to_string()),
            );
        }
        // Open the file in read-only mode
        let file = File::open(&package.spec_file(packaging_dir))?;
        let reader = io::BufReader::new(file);

        // Iterate over each line in the file
        for line in reader.lines() {
            let line = line?;
            // Check if the line starts with "Requires:"
            if line.starts_with("Requires:") {
                let dep = line.split(" ").last().unwrap().to_string();
                // println!("Dep: '{}'", &dep);
                if !nodes.contains_key(&dep) {
                    // println!("Dep not found in nodes: {}", &dep);
                    nodes.insert(dep.to_string(), graph.add_node(dep.clone()));
                }
                graph.add_edge(
                    *nodes.get(package.package_name()).unwrap(),
                    *nodes.get(&dep).unwrap(),
                    (),
                );
            }
        }
    }

    // Convert the graph to DOT format
    let dot = Dot::with_config(&graph, &[Config::EdgeNoLabel]);

    // Write the DOT file
    let mut file = File::create("graph.dot").expect("Unable to create file");
    write!(file, "{:?}", dot).expect("Unable to write to file");

    println!("Graph saved to graph.dot. Attempting to convert to image (make sure graphviz is installed)...");
    let _ = Command::new("dot")
        .arg("-Tpng")
        .arg(Path::new("graph.dot"))
        .arg("-o")
        .arg(Path::new("dep_graph.png"))
        .status();
    Ok(())
}

async fn setup_build_command(
    workdir: &Path,
    package_name: &str,
    srpm_url: Option<&str>,
    version: Option<&str>,
    build_branch: Option<&str>,
    source_branch: Option<&str>,
    auto_srpm: bool,
) -> anyhow::Result<()> {
    let _ = create_dir(workdir);
    let rpm_path = workdir.join(&format!("{}.rpm", package_name));
    let package_folder = workdir.join(package_name);
    println!("fedpkg clone {}", package_name);
    if !Command::new("fedpkg")
        .current_dir(workdir)
        .arg("clone")
        .arg(package_name)
        .status()
        .unwrap()
        .success()
    {
        panic!("Failed: fedpkg clone {}", package_name);
    }
    if let Some(build_branch) = build_branch {
        println!("fedpkg switch-branch {}", build_branch);
        if !Command::new("fedpkg")
            .current_dir(&package_folder)
            .arg("switch-branch")
            .arg(build_branch)
            .status()
            .unwrap()
            .success()
        {
            panic!("Failed: fedpkg switch-branch {}", build_branch);
        }
    }
    if let Some(source_branch) = source_branch {
        println!("git reset --hard {}", source_branch);
        if !Command::new("git")
            .current_dir(&package_folder)
            .arg("reset")
            .arg("--hard")
            .arg(source_branch)
            .status()
            .unwrap()
            .success()
        {
            panic!("Failed: git reset --hard {}", source_branch);
        }
        println!("fedpkg push --force");
        if !Command::new("fedpkg")
            .current_dir(&package_folder)
            .arg("push")
            .arg("--force")
            .status()
            .unwrap()
            .success()
        {
            panic!("Failed: fedpkg push --force");
        }
    }
    let srpm_url = if auto_srpm {
        if srpm_url.is_some() {
            println!("WARNING: srpm url ignored because --auto-srpm was specified");
        }
        let url = format!("https://copr.fedorainfracloud.org/api_3/package/?ownername=ryanabx&projectname=cosmic-epoch-tagged&packagename={}&with_latest_succeeded_build=true", package_name);
        let response = reqwest::get(url)
            .await
            .unwrap()
            .json::<serde_json::Value>()
            .await
            .unwrap();
        println!(
            "Response from api: {}",
            serde_json::to_string_pretty(&response)?
        );
        let url = response
            .get("builds")
            .unwrap()
            .get("latest_succeeded")
            .unwrap()
            .get("source_package")
            .unwrap()
            .get("url")
            .unwrap()
            .as_str()
            .unwrap()
            .to_string();
        Some(url)
    } else {
        srpm_url.map(|s| s.to_string())
    };
    if let Some(srpm_url) = srpm_url {
        println!("wget -O {:?} {}", &rpm_path, srpm_url);
        if !Command::new("wget")
            .current_dir(workdir)
            .arg("-O")
            .arg(&rpm_path)
            .arg(&srpm_url)
            .status()
            .unwrap()
            .success()
        {
            panic!("Failed: wget -O {:?} {}", &rpm_path, &srpm_url);
        }
        println!("fedpkg import --skip-diffs {:?}", &rpm_path);
        if !Command::new("fedpkg")
            .current_dir(&package_folder)
            .arg("import")
            .arg("--skip-diffs")
            .arg(&rpm_path)
            .status()
            .unwrap()
            .success()
        {
            panic!("Failed: fedpkg import --skip-diffs {:?}", &rpm_path);
        }
        let commit_msg = format!("\"Update to {}\"", version.unwrap_or(&srpm_url));
        println!("fedpkg commit -m {}", &commit_msg);
        if !Command::new("fedpkg")
            .current_dir(&package_folder)
            .arg("commit")
            .arg("-m")
            .arg(&commit_msg)
            .status()
            .unwrap()
            .success()
        {
            panic!("Failed: fedpkg commit -m {}", &commit_msg);
        }
        println!("fedpkg push");
        if !Command::new("fedpkg")
            .current_dir(&package_folder)
            .arg("push")
            .status()
            .unwrap()
            .success()
        {
            panic!("Failed: fedpkg push");
        }
    }
    println!("fedpkg build");
    let mut handle = Command::new("fedpkg")
        .current_dir(&package_folder)
        .arg("build")
        .spawn()
        .unwrap();
    println!("Waiting 10 secs for the build to commence");
    thread::sleep(Duration::from_secs(10));
    handle.kill().unwrap();
    Ok(())
}

fn autobump_releases_command(packaging_dir: &Path, release: &str) -> anyhow::Result<()> {
    for package in PACKAGES_ITER {
        homebrew_sed(
            &package.spec_file(packaging_dir),
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
                r##"cargo tree --workspace --edges no-build,no-dev,no-proc-macro --no-dedupe --target all --prefix none --format "{l}""##
            ).output()?;

            let (stdout, _stderr) = (
                String::from_utf8(output.stdout).unwrap(),
                String::from_utf8(output.stderr).unwrap(),
            );
            let mut license_result = stdout
                .lines()
                .collect::<HashSet<&str>>()
                .into_iter()
                .filter_map(|l| {
                    if l == "GPL-3.0" && exclude_gpl_3 {
                        println!("Skipping raw GPL-3.0");
                        return None;
                    }
                    let mut repl_or = l.replace(" / ", " OR ");
                    repl_or = repl_or.replace("/", " OR ");

                    if repl_or.trim().is_empty() {
                        None
                    } else {
                        Some(repl_or.trim().to_string())
                    }
                })
                .collect::<HashSet<String>>()
                .into_iter()
                .map(|license| {
                    let mut sub_licenses = license
                        .split("OR")
                        .map(|sub_license| sub_license.trim().to_string())
                        .collect::<Vec<String>>();
                    sub_licenses.sort();
                    sub_licenses.join(" OR ").trim().to_string()
                })
                .collect::<HashSet<String>>()
                .into_iter()
                .collect::<Vec<String>>();
            license_result.sort();
            let license_result = license_result
                .iter()
                .map(|license| {
                    if license.contains("OR") {
                        format!("({})", license)
                    } else {
                        license.clone()
                    }
                })
                .collect::<Vec<_>>()
                .join(" AND ");
            if let Some(packaging_dir) = packaging_dir.as_deref() {
                if !license_result.is_empty() && license_validate(&license_result)? {
                    homebrew_sed(
                        &package.spec_file(packaging_dir),
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

fn license_validate(license: &str) -> anyhow::Result<bool> {
    let out = Command::new("license-validate")
        .arg("-v")
        .arg(license)
        .output()?;
    let (stdout, stderr) = (
        String::from_utf8(out.stdout)?,
        String::from_utf8(out.stderr)?,
    );
    let passed_validation = stdout.starts_with("Approved license");
    if passed_validation {
        println!("License passed validation.");
    } else {
        eprintln!("License failed validation: {} {}", &stdout, &stderr);
    }
    Ok(passed_validation)
}
