import java.io.BufferedReader;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class LoadValidatePostedZip {
	public static void main(String[] args) throws IOException {
		String restAPIstr =
			"http://localhost:8080/rest/xbrl/" + 
			"instance-no-formula-link.xml" +
			"/validation/xbrl" +
			"?media=text" +
			"&import=assertionsHtmlSchemaLoc.xml" +
			"&formulaAsserResultCounts";
		URL url = new URL(restAPIstr);
		HttpURLConnection conn =
		      (HttpURLConnection) url.openConnection();
		conn.setRequestMethod("POST");
		conn.setRequestProperty("Content-Type",
				"application/zip");
		conn.setDoOutput(true);
	    //Send request
		File zipFile = new File("C:/temp/test-assertion-example.zip");
		InputStream is = new FileInputStream(zipFile);
		byte[] zipFileBytes = new byte[1000000];
		int countRead = is.read(zipFileBytes, 0, 1000000);
		is.close();

		DataOutputStream wr = new DataOutputStream (
				conn.getOutputStream ());
		wr.write(zipFileBytes, 0, countRead);
		wr.flush ();
		wr.close ();
		
		if (conn.getResponseCode() != 200) {
		    throw new IOException(conn.getResponseMessage());
		}

		// Buffer the result into a string
		BufferedReader rd = new BufferedReader(
		      new InputStreamReader(conn.getInputStream()));
		StringBuilder sb = new StringBuilder();
		String line;
		while ((line = rd.readLine()) != null) {
		    sb.append(line);
			System.out.println(line);
		}
		rd.close();
		conn.disconnect();
	}
}
