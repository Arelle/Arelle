import java.io.BufferedInputStream;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;

public class LoadValidateCmdLine {
	public static void main(String[] args) throws IOException {
		Runtime r = Runtime.getRuntime();
		String arelleExe = "\"C:\\Program Files\\Arelle\\arelleCmdLine.exe\"";
		// XDG_CONFIG_HOME is optional, when omitted it defaults to "~/.config"
		String arelleXdgConfigHome = "C:\\Users\\hermfi~1\\appdir\\local";
		String fileBase = "C:\\Users\\John Doe\\samples\\";
		String [] fileNames = {
				"instance0000010.xml",
				"instance0010000.xml"
				//"instance0020000.xml",
				//"instance0040000.xml",
				//"instance0060000.xml",
				//"instance0080000.xml",
				//"instance0100000.xml",
				//"instance0120000.xml",
				//"instance0165000.xml"
		};
		for (String fileName : fileNames) {
			try {
				System.out.println("File: " + fileName);
				String cmdLine = 
					arelleExe +
					" --file " +
					"\"" + fileBase + fileName + "\"" +
					" -v";
				System.out.println("CmdLine: " + cmdLine);
				String[] envp = new String[1];
				// XDG_CONFIG_HOME is optional, defaults to "~/.config"
				envp[0] = "XDG_CONFIG_HOME=" + arelleXdgConfigHome;
				Process p = r.exec(cmdLine, envp);
				InputStream in = p.getInputStream();
				BufferedInputStream buf = new BufferedInputStream(in);
				InputStreamReader inread = new InputStreamReader(buf);
				BufferedReader br = new BufferedReader(inread);
				
				String line;
				while ((line = br.readLine()) != null) {
					System.out.println(line);
				}
				try {
					if (p.waitFor() != 0) {
						System.err.println("exit value = " + p.exitValue());
						}
				} 
				catch (InterruptedException e) {
					System.err.println(e);
				} 
				finally {
					// Close the InputStream
					br.close();
					inread.close();
					buf.close();
					in.close();
				}
			} 
			catch (IOException e) {
				System.err.println(e.getMessage());
				}
			}
		System.out.println("Done");
	}
}
