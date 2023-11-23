using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Net;
using System.IO;
using System.Diagnostics;

namespace ArelleCsharpProject
{
    class LoadValidate
    {
        static void Main(string[] args)
        {
		    string restAPIstr =
			    "http://localhost:8080/rest/xbrl/" + 
			    "C:/Users/John%20Doe/Samples/instance0010000.xbrl" +
			    "/validation/xbrl?media=text";

            HttpWebRequest req = WebRequest.Create(restAPIstr) as HttpWebRequest;

            string line;
            using (HttpWebResponse resp = req.GetResponse() as HttpWebResponse)
            {
                StreamReader reader = new StreamReader(resp.GetResponseStream());
                while ((line = reader.ReadLine()) != null)
                    Debug.WriteLine(line);
            }
        }
    }
}
