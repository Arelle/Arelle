import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class LoadValidateWebService {
	public static void main(String[] args) throws IOException {
		String restAPIstr =
			"http://localhost:8080/rest/xbrl/" + 
			"C:/Users/John%20Doe/Samples/instance0010000.xbrl" +
			"/validation/xbrl?media=text";
		URL url = new URL(restAPIstr);
		HttpURLConnection conn =
		      (HttpURLConnection) url.openConnection();

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
